from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.parse import parse_requirements, parse_vendor_facts


def make_pdf(path: Path, lines: list[str]):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 22
    c.save()


def test_pdf_requirement_extraction(tmp_path):
    path = tmp_path / "spec.pdf"
    make_pdf(path, ["6.4 Pumps", "Motor efficiency shall be minimum 90 %", "Noise level must not exceed 70 dB"])
    reqs = parse_requirements(path)
    assert len(reqs) == 2
    assert reqs[0].operator == ">="
    assert reqs[0].value == 90
    assert reqs[1].operator == "<="
    assert reqs[1].value == 70

    # Qualitative requirements retain the subject before normative language.
    path2 = tmp_path / "qualitative.pdf"
    make_pdf(path2, ["Housing shall be corrosion resistant"])
    q = parse_requirements(path2)
    assert q[0].parameter == "housing"


def test_vendor_fact_extraction(tmp_path):
    path = tmp_path / "vendor.pdf"
    make_pdf(path, ["Motor efficiency: 93 %", "Noise level: 68 dB", "Housing: 316L stainless steel"])
    facts = parse_vendor_facts(path)
    assert len(facts) == 3
    assert facts[0].value == 93
    assert facts[1].unit == "db"
