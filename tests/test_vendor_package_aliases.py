from __future__ import annotations

from types import SimpleNamespace

import bidlint.cli as cli
from bidlint.models import Requirement, SourceRef, VendorFact
from bidlint.vendor_package import consolidate_package_facts


def _fact(document: str, parameter: str, raw_value: str, value: float, unit: str) -> VendorFact:
    return VendorFact(
        parameter=parameter,
        raw_value=raw_value,
        value=value,
        unit=unit,
        source=SourceRef(document=document, page=1),
    )


def _args() -> SimpleNamespace:
    return SimpleNamespace(ifc_class=None, ifc_guid=None, ifc_pset=None, xlsx_sheet=None)


def test_package_consolidation_uses_project_aliases() -> None:
    facts = [
        _fact("offer.pdf", "supplier rated output", "11 kW", 11, "kW"),
        _fact("datasheet.pdf", "motor power", "11000 W", 11000, "W"),
    ]

    without_aliases, conflicts = consolidate_package_facts("Supplier-A", facts)
    with_aliases, aliased_conflicts = consolidate_package_facts(
        "Supplier-A",
        facts,
        aliases={"supplier rated output": "motor power"},
    )

    assert without_aliases == facts
    assert conflicts == []
    assert with_aliases == [facts[0]]
    assert aliased_conflicts == []


def test_parse_cli_vendor_threads_aliases_into_directory_package(tmp_path, monkeypatch) -> None:
    aliases = {"supplier rated output": "motor power"}
    seen: dict[str, object] = {}

    def fake_parse_vendor_input(path, **kwargs):
        seen["path"] = path
        seen["kwargs"] = kwargs
        return []

    monkeypatch.setattr(cli, "parse_vendor_input", fake_parse_vendor_input)

    assert cli._parse_cli_vendor(str(tmp_path), _args(), aliases=aliases) == []
    assert seen["path"] == str(tmp_path)
    assert seen["kwargs"] == {
        "ifc_class": None,
        "ifc_guid": None,
        "ifc_pset": None,
        "xlsx_sheet": None,
        "aliases": aliases,
    }


def test_compare_main_passes_loaded_aliases_to_vendor_parser(monkeypatch) -> None:
    aliases = {"supplier rated output": "motor power"}
    requirement = Requirement(
        id="R0001",
        text="Motor power shall be minimum 10 kW.",
        parameter="motor power",
        operator=">=",
        value=10,
        unit="kW",
    )
    vendor_fact = _fact("offer.pdf", "supplier rated output", "11 kW", 11, "kW")
    seen: list[object] = []

    monkeypatch.setattr(cli, "parse_requirements", lambda _: [requirement])
    monkeypatch.setattr(cli, "load_alias_file", lambda _: aliases)

    def fake_parse_cli_vendor(vendor, args, *, mixed_rank=False, aliases=None):
        seen.append((vendor, mixed_rank, aliases))
        return [vendor_fact]

    monkeypatch.setattr(cli, "_parse_cli_vendor", fake_parse_cli_vendor)

    assert cli.main(["compare", "spec.pdf", "Supplier-A", "--aliases", "aliases.json"]) == 0
    assert seen == [("Supplier-A", False, aliases)]


def test_rank_main_passes_loaded_aliases_to_every_vendor_parser(monkeypatch) -> None:
    aliases = {"supplier rated output": "motor power"}
    requirement = Requirement(
        id="R0001",
        text="Motor power shall be minimum 10 kW.",
        parameter="motor power",
        operator=">=",
        value=10,
        unit="kW",
    )
    vendor_fact = _fact("offer.pdf", "supplier rated output", "11 kW", 11, "kW")
    seen: list[object] = []

    monkeypatch.setattr(cli, "parse_requirements", lambda _: [requirement])
    monkeypatch.setattr(cli, "load_alias_file", lambda _: aliases)

    def fake_parse_cli_vendor(vendor, args, *, mixed_rank=False, aliases=None):
        seen.append((vendor, mixed_rank, aliases))
        return [vendor_fact]

    monkeypatch.setattr(cli, "_parse_cli_vendor", fake_parse_cli_vendor)

    assert cli.main(["rank", "spec.pdf", "Supplier-A", "Supplier-B", "--aliases", "aliases.json"]) == 0
    assert seen == [
        ("Supplier-A", True, aliases),
        ("Supplier-B", True, aliases),
    ]
