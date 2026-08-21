from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.compare import compare
from bidlint.models import Status
from bidlint.parse import parse_requirements, parse_vendor_facts


def _make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def test_external_derived_grade_and_load_class_remain_qualitative(tmp_path):
    """Minimized, identity-free pattern derived from a real external drainage tender corpus."""
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(
        specification,
        [
            "Channel material shall be Grade 304 stainless steel",
            "Channel load class shall be A15",
            "Channel grating shall be plain ladder grating",
        ],
    )
    _make_pdf(
        vendor,
        [
            "Channel material: 304 grade stainless steel",
            "Channel load class: A15",
            "Channel grating: plain ladder grating",
        ],
    )

    requirements = parse_requirements(specification)
    facts = parse_vendor_facts(vendor)

    assert [requirement.parameter for requirement in requirements] == [
        "channel material",
        "channel load class",
        "channel grating",
    ]
    assert all(requirement.operator is None for requirement in requirements)
    assert all(requirement.value is None for requirement in requirements)

    by_parameter = {fact.parameter: fact for fact in facts}
    assert by_parameter["channel material"].value is None
    assert by_parameter["channel material"].unit is None
    assert by_parameter["channel load class"].value is None
    assert by_parameter["channel load class"].unit is None

    report = compare(requirements, facts, specification.name, vendor.name)
    assert [finding.status for finding in report.findings] == [Status.REVIEW, Status.REVIEW, Status.REVIEW]
    assert report.counts == {"PASS": 0, "DEVIATION": 0, "MISSING": 0, "REVIEW": 3}
