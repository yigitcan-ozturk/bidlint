from bidlint.compare import compare
from bidlint.models import Requirement, SourceRef, Status, VendorFact
from bidlint.units import canonical_unit, convert_value


def req(parameter, operator, value, unit=None):
    return Requirement(
        "R0001",
        f"{parameter} {operator} {value}",
        parameter,
        operator,
        value,
        unit,
        True,
        SourceRef("spec.pdf", 1),
    )


def fact(parameter, value, unit=None):
    return VendorFact(parameter, f"{value}{unit or ''}", value, unit, SourceRef("vendor.pdf", 1))


def test_minimum_passes():
    report = compare(
        [req("motor efficiency", ">=", 90, "%")],
        [fact("motor efficiency", 93, "%")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.PASS
    assert report.compliance_score == 100.0


def test_minimum_deviation():
    report = compare(
        [req("motor efficiency", ">=", 90, "%")],
        [fact("motor efficiency", 85, "%")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.DEVIATION
    assert report.compliance_score == 0.0


def test_missing_parameter():
    report = compare(
        [req("ip rating", ">=", 65)],
        [fact("motor power", 11, "kw")],
        "spec.pdf",
        "vendor.pdf",
        threshold=0.7,
    )
    assert report.findings[0].status == Status.MISSING


def test_qualitative_requires_review():
    requirement = Requirement(
        "R0001",
        "Housing shall be corrosion resistant",
        "housing",
        None,
        None,
        None,
        True,
        SourceRef("spec.pdf", 1),
    )
    report = compare(
        [requirement],
        [VendorFact("housing", "316L stainless steel", None, None, SourceRef("vendor.pdf", 2))],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.REVIEW


def test_power_conversion_passes_and_explains_conversion():
    report = compare(
        [req("motor power", ">=", 10, "kw")],
        [fact("motor power", 10000, "w")],
        "spec.pdf",
        "vendor.pdf",
    )
    finding = report.findings[0]
    assert finding.status == Status.PASS
    assert "10000w (= 10kw)" in finding.reason


def test_pressure_conversion_detects_deviation():
    report = compare(
        [req("design pressure", ">=", 10, "bar")],
        [fact("design pressure", 900, "kpa")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.DEVIATION


def test_flow_conversion_between_m3h_and_ls():
    report = compare(
        [req("flow rate", ">=", 10, "l/s")],
        [fact("flow rate", 36, "m3/h")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.PASS


def test_incompatible_dimensions_remain_review():
    report = compare(
        [req("motor power", ">=", 10, "kw")],
        [fact("motor power", 10, "bar")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.REVIEW


def test_unit_helpers_are_explicit_and_dimension_safe():
    assert canonical_unit("m3/h") == "m³/h"
    assert convert_value(1000, "w", "kw") == 1
    assert convert_value(1, "bar", "kpa") == 100
    assert convert_value(36, "m3/h", "l/s") == 10
    assert convert_value(1, "kw", "bar") is None


def test_report_renderers_and_portfolio_json():
    from bidlint.report import portfolio_to_json, to_html

    report_a = compare(
        [req("motor efficiency", ">=", 90, "%")],
        [fact("motor efficiency", 93, "%")],
        "spec.pdf",
        "vendor-a.pdf",
    )
    report_b = compare(
        [req("motor efficiency", ">=", 90, "%")],
        [fact("motor efficiency", 85, "%")],
        "spec.pdf",
        "vendor-b.pdf",
    )
    rendered = to_html(report_a)
    assert "Compliance matrix" in rendered
    assert "vendor-a.pdf" in rendered
    portfolio = portfolio_to_json([report_b, report_a])
    assert portfolio.index("vendor-a.pdf") < portfolio.index("vendor-b.pdf")
