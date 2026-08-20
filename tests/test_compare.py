import pytest

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


def test_flow_conversion_supports_litres_per_minute():
    report = compare(
        [req("flow rate", ">=", 1, "l/s")],
        [fact("flow rate", 60, "l/min")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.PASS


def test_electrical_conversion_passes_end_to_end():
    report = compare(
        [req("supply voltage", ">=", 0.4, "kv")],
        [fact("supply voltage", 400, "v")],
        "spec.pdf",
        "vendor.pdf",
    )
    finding = report.findings[0]
    assert finding.status == Status.PASS
    assert "400v (= 0.4kv)" in finding.reason


def test_temperature_conversion_is_affine_and_explicit():
    report = compare(
        [req("operating temperature", "<=", 40, "°c")],
        [fact("operating temperature", 104, "°f")],
        "spec.pdf",
        "vendor.pdf",
    )
    finding = report.findings[0]
    assert finding.status == Status.PASS
    assert "104°f (= 40°c)" in finding.reason
    assert convert_value(0, "°c", "k") == pytest.approx(273.15)
    assert convert_value(32, "°f", "°c") == pytest.approx(0)


def test_extended_linear_unit_families():
    assert convert_value(2500, "mA", "A") == pytest.approx(2.5)
    assert convert_value(0.05, "kHz", "Hz") == pytest.approx(50)
    assert convert_value(0.4, "MVA", "kVA") == pytest.approx(400)
    assert convert_value(1, "psi", "kPa") == pytest.approx(6.894757293168)
    assert convert_value(12, "in", "mm") == pytest.approx(304.8)
    assert convert_value(1, "t", "kg") == pytest.approx(1000)
    assert convert_value(2.5, "kN", "N") == pytest.approx(2500)


def test_new_aliases_remain_conservative():
    assert canonical_unit("kilovolt") == "kv"
    assert canonical_unit("rev/min") == "rpm"
    assert canonical_unit("metric tonne") == "t"
    assert canonical_unit("PSIG") == "psig"
    assert convert_value(10, "psig", "bar") is None
    assert convert_value(400, "v", "a") is None
    assert convert_value(10, "kw", "kva") is None
    assert convert_value(68, "f", "°c") is None


def test_incompatible_dimensions_remain_review():
    report = compare(
        [req("motor power", ">=", 10, "kw")],
        [fact("motor power", 10, "bar")],
        "spec.pdf",
        "vendor.pdf",
    )
    assert report.findings[0].status == Status.REVIEW


def test_missing_unit_evidence_remains_review():
    report = compare(
        [req("motor power", ">=", 10, "kw")],
        [fact("motor power", 12)],
        "spec.pdf",
        "vendor.pdf",
    )
    finding = report.findings[0]
    assert finding.status == Status.REVIEW
    assert "Units require review" in finding.reason


def test_unit_helpers_are_explicit_and_dimension_safe():
    assert canonical_unit("m3/h") == "m³/h"
    assert canonical_unit("LPM") == "l/min"
    assert convert_value(1000, "w", "kw") == 1
    assert convert_value(1, "bar", "kpa") == 100
    assert convert_value(36, "m3/h", "l/s") == 10
    assert convert_value(60, "l/min", "l/s") == 1
    assert convert_value(1, "kw", "bar") is None
    assert convert_value(10, None, "kw") is None
    assert convert_value(10, None, None) == 10


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
