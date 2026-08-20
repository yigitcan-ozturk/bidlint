from __future__ import annotations

from types import SimpleNamespace

import pytest

import bidlint.inputs as inputs
import bidlint.vendor_package as vendor_package
from bidlint.compare import compare
from bidlint.models import Requirement, SourceRef, Status, VendorFact
from bidlint.vendor_package import consolidate_package_facts, parse_vendor_package


def _fact(
    document: str,
    parameter: str,
    raw_value: str,
    *,
    value: float | None = None,
    unit: str | None = None,
    page: int | None = None,
    line: int | None = None,
) -> VendorFact:
    return VendorFact(
        parameter=parameter,
        raw_value=raw_value,
        value=value,
        unit=unit,
        source=SourceRef(document=document, page=page, line=line),
    )


def test_vendor_package_discovers_supported_direct_children_in_name_order(tmp_path, monkeypatch) -> None:
    (tmp_path / "B.pdf").write_bytes(b"")
    (tmp_path / "a.xlsx").write_bytes(b"")
    (tmp_path / "commercial.docx").write_bytes(b"")

    calls: list[str] = []

    def fake_pdf(path):
        calls.append(path.name)
        return [_fact(path.name, "flow rate", "20 L/s", value=20, unit="L/s")]

    def fake_xlsx(path, *, sheet=None):
        calls.append(path.name)
        assert sheet is None
        return [_fact(path.name, "motor power", "11 kW", value=11, unit="kW")]

    monkeypatch.setattr(vendor_package, "parse_vendor_facts", fake_pdf)
    monkeypatch.setattr(vendor_package, "parse_xlsx_vendor_facts", fake_xlsx)

    package = parse_vendor_package(tmp_path)

    assert calls == ["a.xlsx", "B.pdf"]
    assert [path.name for path in package.documents] == ["a.xlsx", "B.pdf"]
    assert [path.name for path in package.ignored_documents] == ["commercial.docx"]
    assert [fact.parameter for fact in package.facts] == ["motor power", "flow rate"]
    assert package.conflicts == []


def test_equivalent_numeric_package_facts_collapse_across_units() -> None:
    facts = [
        _fact("motor.pdf", "motor power", "11 kW", value=11, unit="kW", page=2),
        _fact("offer.xlsx", "rated motor power", "11000 W", value=11000, unit="W", line=7),
    ]

    consolidated, conflicts = consolidate_package_facts("Supplier-A", facts)

    assert consolidated == [facts[0]]
    assert conflicts == []


def test_conflicting_package_facts_force_existing_evaluator_to_review() -> None:
    facts = [
        _fact("motor.pdf", "motor power", "11 kW", value=11, unit="kW", page=2),
        _fact("offer.xlsx", "rated motor power", "15 kW", value=15, unit="kW", line=7),
    ]
    consolidated, conflicts = consolidate_package_facts("Supplier-A", facts)
    requirement = Requirement(
        id="R0001",
        text="Motor power shall be minimum 10 kW.",
        parameter="motor power",
        operator=">=",
        value=10,
        unit="kW",
    )

    report = compare([requirement], consolidated, "specification.pdf", "Supplier-A")

    assert len(conflicts) == 1
    assert report.findings[0].status is Status.REVIEW
    assert report.findings[0].vendor_fact is conflicts[0]
    assert "motor.pdf:page 2 = 11 kW" in report.findings[0].reason
    assert "offer.xlsx:line 7 = 15 kW" in report.findings[0].reason


def test_vendor_input_dispatches_directories_to_package_parser(tmp_path, monkeypatch) -> None:
    fact = _fact("offer.pdf", "flow rate", "20 L/s", value=20, unit="L/s")

    def fake_package(path, **kwargs):
        assert path == tmp_path
        assert kwargs == {"ifc_class": None, "ifc_guid": None, "ifc_pset": None, "xlsx_sheet": None}
        return SimpleNamespace(facts=[fact])

    monkeypatch.setattr(inputs, "parse_vendor_package", fake_package)

    assert inputs.parse_vendor_input(tmp_path) == [fact]


def test_vendor_package_rejects_directory_without_supported_documents(tmp_path) -> None:
    (tmp_path / "commercial.docx").write_bytes(b"")

    with pytest.raises(ValueError, match=r"no supported \.pdf, \.ifc or \.xlsx files"):
        parse_vendor_package(tmp_path)
