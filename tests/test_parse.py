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


def test_vendor_colon_fact_extraction_keeps_material_grade_qualitative(tmp_path):
    path = tmp_path / "vendor.pdf"
    make_pdf(path, ["Motor efficiency: 93 %", "Noise level: 68 dB", "Housing: 316L stainless steel"])
    facts = parse_vendor_facts(path)
    assert len(facts) == 3
    assert facts[0].value == 93
    assert facts[1].unit == "db"
    assert facts[2].raw_value == "316L stainless steel"
    assert facts[2].value is None
    assert facts[2].unit is None


def test_vendor_two_column_rows(tmp_path):
    path = tmp_path / "two-column.pdf"
    make_pdf(
        path,
        [
            "Motor power        11 kW",
            "Design pressure        10 bar",
            "Housing material        316L stainless steel",
        ],
    )
    facts = parse_vendor_facts(path)
    assert [fact.parameter for fact in facts] == ["motor power", "design pressure", "housing material"]
    assert facts[0].value == 11
    assert facts[0].unit == "kw"
    assert facts[1].value == 10
    assert facts[1].unit == "bar"
    assert facts[2].value is None


def test_vendor_label_then_numeric_value_on_next_line(tmp_path):
    path = tmp_path / "paired-numeric.pdf"
    make_pdf(path, ["Motor power", "11000 W", "Noise level", "68 dB"])
    facts = parse_vendor_facts(path)
    assert len(facts) == 2
    assert facts[0].parameter == "motor power"
    assert facts[0].value == 11000
    assert facts[0].unit == "w"
    assert facts[1].parameter == "noise level"
    assert facts[1].value == 68
    assert facts[1].unit == "db"


def test_vendor_colon_label_can_take_qualitative_next_line(tmp_path):
    path = tmp_path / "paired-qualitative.pdf"
    make_pdf(path, ["Housing material:", "316L stainless steel", "Coating:", "Epoxy powder coat"])
    facts = parse_vendor_facts(path)
    assert len(facts) == 2
    assert facts[0].parameter == "housing material"
    assert facts[0].raw_value == "316L stainless steel"
    assert facts[0].value is None
    assert facts[1].parameter == "coating"
    assert facts[1].raw_value == "Epoxy powder coat"


def test_plain_headings_are_not_paired_as_vendor_facts(tmp_path):
    path = tmp_path / "headings.pdf"
    make_pdf(path, ["TECHNICAL DATA", "Pump Series AX", "GENERAL NOTES", "For indoor installation"])
    assert parse_vendor_facts(path) == []
