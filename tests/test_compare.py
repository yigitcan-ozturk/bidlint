from bidlint.compare import compare
from bidlint.models import Requirement, SourceRef, Status, VendorFact


def req(parameter, operator, value, unit=None):
    return Requirement("R0001", f"{parameter} {operator} {value}", parameter, operator, value, unit, True, SourceRef("spec.pdf", 1))


def fact(parameter, value, unit=None):
    return VendorFact(parameter, f"{value}{unit or ''}", value, unit, SourceRef("vendor.pdf", 1))


def test_minimum_passes():
    report = compare([req("motor efficiency", ">=", 90, "%")], [fact("motor efficiency", 93, "%")], "spec.pdf", "vendor.pdf")
    assert report.findings[0].status == Status.PASS
    assert report.compliance_score == 100.0


def test_minimum_deviation():
    report = compare([req("motor efficiency", ">=", 90, "%")], [fact("motor efficiency", 85, "%")], "spec.pdf", "vendor.pdf")
    assert report.findings[0].status == Status.DEVIATION
    assert report.compliance_score == 0.0


def test_missing_parameter():
    report = compare([req("ip rating", ">=", 65)], [fact("motor power", 11, "kw")], "spec.pdf", "vendor.pdf", threshold=0.7)
    assert report.findings[0].status == Status.MISSING


def test_qualitative_requires_review():
    requirement = Requirement("R0001", "Housing shall be corrosion resistant", "housing", None, None, None, True, SourceRef("spec.pdf", 1))
    report = compare([requirement], [VendorFact("housing", "316L stainless steel", None, None, SourceRef("vendor.pdf", 2))], "spec.pdf", "vendor.pdf")
    assert report.findings[0].status == Status.REVIEW


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
