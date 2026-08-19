import json

import pytest

from bidlint.cli import build_parser
from bidlint.compare import compare
from bidlint.models import Requirement, SourceRef, Status, VendorFact
from bidlint.terminology import canonical_parameter, load_alias_file


def req(parameter, value=65, unit=None):
    return Requirement(
        "R0001",
        f"{parameter} >= {value}",
        parameter,
        ">=",
        value,
        unit,
        True,
        SourceRef("spec.pdf", 1),
    )


def fact(parameter, value=65, unit=None):
    return VendorFact(parameter, f"{value}{unit or ''}", value, unit, SourceRef("vendor.pdf", 1))


def test_builtin_ip_terminology_matches_explicit_ingress_protection_term():
    report = compare(
        [req("ip rating")],
        [fact("ingress protection rating")],
        "spec.pdf",
        "vendor.pdf",
    )
    finding = report.findings[0]
    assert finding.status == Status.PASS
    assert finding.confidence == 1.0


def test_ambiguous_protection_class_is_not_treated_as_ip_rating():
    assert canonical_parameter("protection class") == "protection class"
    report = compare(
        [req("ip rating")],
        [fact("protection class")],
        "spec.pdf",
        "vendor.pdf",
        threshold=0.7,
    )
    assert report.findings[0].status == Status.MISSING


def test_builtin_mechanical_and_electrical_terms_are_conservative():
    assert canonical_parameter("Flow-rate") == "flow rate"
    assert canonical_parameter("rotation speed") == "rotational speed"
    assert canonical_parameter("rated motor power") == "motor power"

    report = compare(
        [req("motor power", 10, "kw")],
        [fact("rated motor power", 10000, "w")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.PASS


def test_custom_aliases_can_map_project_or_vendor_nomenclature():
    report = compare(
        [req("motor power", 10, "kw")],
        [fact("rated output", 11, "kw")],
        "spec.pdf",
        "vendor.pdf",
        aliases={"rated output": "motor power"},
    )
    finding = report.findings[0]
    assert finding.status == Status.PASS
    assert finding.confidence == 1.0


def test_alias_file_loading_and_normalization(tmp_path):
    path = tmp_path / "aliases.json"
    path.write_text(
        json.dumps({"Supplier Rated Output": "Motor Power", "Ingress-Protection Code": "IP Rating"}),
        encoding="utf-8",
    )
    aliases = load_alias_file(path)
    assert aliases == {
        "supplier rated output": "motor power",
        "ingress protection code": "ip rating",
    }
    assert canonical_parameter("Supplier Rated Output", aliases) == "motor power"


def test_invalid_alias_file_is_rejected(tmp_path):
    path = tmp_path / "aliases.json"
    path.write_text('["not", "an", "object"]', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_alias_file(path)


def test_cli_accepts_alias_files_for_compare_and_rank():
    parser = build_parser()
    compare_args = parser.parse_args(["compare", "spec.pdf", "vendor.pdf", "--aliases", "aliases.json"])
    rank_args = parser.parse_args(["rank", "spec.pdf", "a.pdf", "b.pdf", "--aliases", "aliases.json"])
    assert compare_args.aliases == "aliases.json"
    assert rank_args.aliases == "aliases.json"
