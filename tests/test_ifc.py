import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import bidlint.ifc as ifc_module
from bidlint.cli import main
from bidlint.compare import compare
from bidlint.ifc import parse_ifc_facts
from bidlint.inputs import parse_vendor_input
from bidlint.models import Requirement, SourceRef, Status


class FakeEntity:
    def __init__(self, ifc_class: str, guid: str, name: str) -> None:
        self.ifc_class = ifc_class
        self.GlobalId = guid
        self.Name = name

    def is_a(self, ifc_class: str | None = None):
        if ifc_class is None:
            return self.ifc_class
        return ifc_class == self.ifc_class


class FakeModel:
    def __init__(self, entities: list[FakeEntity]) -> None:
        self.entities = entities

    def by_type(self, ifc_class: str):
        if not ifc_class.startswith("Ifc"):
            raise RuntimeError("unknown schema class")
        return [entity for entity in self.entities if entity.is_a(ifc_class)]

    def by_guid(self, guid: str):
        for entity in self.entities:
            if entity.GlobalId == guid:
                return entity
        raise RuntimeError("guid not found")


def install_fake_ifc(monkeypatch, model: FakeModel, psets: dict[str, dict]) -> None:
    fake_module = SimpleNamespace(open=lambda _path: model)

    def get_psets(entity, *, psets_only: bool, should_inherit: bool):
        assert psets_only is True
        assert should_inherit is True
        return psets[entity.GlobalId]

    monkeypatch.setattr(ifc_module, "_load_ifc_api", lambda: (fake_module, get_psets))


def make_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 22
    c.save()


def test_ifc_properties_become_source_traceable_vendor_facts(tmp_path, monkeypatch):
    path = tmp_path / "pump.ifc"
    path.write_text("ISO-10303-21;", encoding="utf-8")
    pump = FakeEntity("IfcPump", "1PumpGuid0000000000000", "Primary Pump")
    model = FakeModel([pump])
    install_fake_ifc(
        monkeypatch,
        model,
        {
            pump.GlobalId: {
                "Pset_PumpCommon": {
                    "id": 123,
                    "MotorPower": "11 kW",
                    "DesignPressure": 10,
                    "Status": "NEW",
                    "Enabled": True,
                    "Complex": {"nested": "ignored"},
                    "Missing": None,
                }
            }
        },
    )

    facts = parse_ifc_facts(path, ifc_class="IfcPump")
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [
        ("design pressure", "10"),
        ("enabled", "true"),
        ("motor power", "11 kW"),
        ("status", "NEW"),
    ]
    motor = next(fact for fact in facts if fact.parameter == "motor power")
    assert motor.value == 11
    assert motor.unit == "kw"
    pressure = next(fact for fact in facts if fact.parameter == "design pressure")
    assert pressure.value == 10
    assert pressure.unit is None
    assert motor.source == SourceRef(
        document="pump.ifc",
        section=f"IfcPump:{pump.GlobalId}/Pset_PumpCommon",
    )


def test_ifc_guid_and_pset_scope_are_explicit(tmp_path, monkeypatch):
    path = tmp_path / "equipment.ifc"
    path.write_text("ISO-10303-21;", encoding="utf-8")
    pump = FakeEntity("IfcPump", "1PumpGuid0000000000000", "Pump")
    fan = FakeEntity("IfcFan", "1FanGuid00000000000000", "Fan")
    model = FakeModel([pump, fan])
    install_fake_ifc(
        monkeypatch,
        model,
        {
            pump.GlobalId: {
                "Pset_PumpCommon": {"FlowRate": "125 m3/h"},
                "Pset_ManufacturerTypeInformation": {"ModelReference": "PX-125"},
            },
            fan.GlobalId: {"Pset_FanCommon": {"AirFlowRate": "500 m3/h"}},
        },
    )

    facts = parse_ifc_facts(path, global_id=pump.GlobalId, pset="Pset_PumpCommon")
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [("flow rate", "125 m3/h")]

    with pytest.raises(ValueError, match="requires --ifc-class or --ifc-guid"):
        parse_ifc_facts(path)
    with pytest.raises(ValueError, match="not IfcFan"):
        parse_ifc_facts(path, global_id=pump.GlobalId, ifc_class="IfcFan")
    with pytest.raises(ValueError, match="GlobalId not found"):
        parse_ifc_facts(path, global_id="missing")
    with pytest.raises(ValueError, match="property set"):
        parse_ifc_facts(path, global_id=pump.GlobalId, pset="Pset_Missing")


def test_ifc_class_scope_rejects_multiple_vendor_elements(tmp_path, monkeypatch):
    path = tmp_path / "pumps.ifc"
    path.write_text("ISO-10303-21;", encoding="utf-8")
    pump_a = FakeEntity("IfcPump", "1PumpGuid0000000000000", "Pump A")
    pump_b = FakeEntity("IfcPump", "2PumpGuid0000000000000", "Pump B")
    model = FakeModel([pump_a, pump_b])
    install_fake_ifc(
        monkeypatch,
        model,
        {
            pump_a.GlobalId: {"Pset_PumpCommon": {"MotorPower": "11 kW"}},
            pump_b.GlobalId: {"Pset_PumpCommon": {"MotorPower": "15 kW"}},
        },
    )

    with pytest.raises(ValueError, match="matched 2 elements; use --ifc-guid"):
        parse_ifc_facts(path, ifc_class="IfcPump")


def test_ifc_fact_flows_through_unchanged_deterministic_compare(tmp_path, monkeypatch):
    path = tmp_path / "pump.ifc"
    path.write_text("ISO-10303-21;", encoding="utf-8")
    pump = FakeEntity("IfcPump", "1PumpGuid0000000000000", "Pump")
    model = FakeModel([pump])
    install_fake_ifc(
        monkeypatch,
        model,
        {pump.GlobalId: {"Pset_PumpCommon": {"MotorPower": "11 kW"}}},
    )

    facts = parse_ifc_facts(path, global_id=pump.GlobalId)
    requirement = Requirement(
        id="R0001",
        text="Motor power shall be minimum 10 kW",
        parameter="motor power",
        operator=">=",
        value=10,
        unit="kw",
    )
    report = compare([requirement], facts, "spec.pdf", path.name)
    assert report.findings[0].status == Status.PASS
    assert report.compliance_score == 100.0


def test_cli_compares_specification_pdf_with_scoped_ifc_vendor(tmp_path, monkeypatch, capsys):
    specification = tmp_path / "spec.pdf"
    vendor = tmp_path / "pump.ifc"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    vendor.write_text("ISO-10303-21;", encoding="utf-8")
    pump = FakeEntity("IfcPump", "1PumpGuid0000000000000", "Pump")
    model = FakeModel([pump])
    install_fake_ifc(
        monkeypatch,
        model,
        {pump.GlobalId: {"Pset_PumpCommon": {"MotorPower": "11 kW"}}},
    )

    exit_code = main(["compare", str(specification), str(vendor), "--ifc-guid", pump.GlobalId, "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["vendor"] == "pump.ifc"
    assert payload["compliance_score"] == 100.0
    assert payload["findings"][0]["status"] == "PASS"


def test_vendor_input_dispatch_rejects_ifc_options_for_pdf(tmp_path):
    vendor = tmp_path / "vendor.pdf"
    make_pdf(vendor, ["Motor power: 11 kW"])
    facts = parse_vendor_input(vendor)
    assert facts[0].parameter == "motor power"

    with pytest.raises(ValueError, match="only be used with .ifc"):
        parse_vendor_input(vendor, ifc_class="IfcPump")

    unsupported = tmp_path / "vendor.txt"
    unsupported.write_text("Motor power: 11 kW", encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.pdf, \.ifc or \.xlsx"):
        parse_vendor_input(unsupported)
