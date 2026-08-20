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


def make_positioned_pdf(path: Path, rows: list[list[str]], xs: list[int]):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for row in rows:
        for x, text in zip(xs, row, strict=True):
            c.drawString(x, y, text)
        y -= 24
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


def test_layout_table_uses_offered_column_and_separate_unit(tmp_path):
    path = tmp_path / "table.pdf"
    make_positioned_pdf(
        path,
        [
            ["Parameter", "Unit", "Required", "Offered"],
            ["Motor power", "kW", ">= 10", "11"],
            ["Design pressure", "bar", ">= 10", "10"],
        ],
        [50, 250, 330, 430],
    )
    facts = parse_vendor_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [
        ("motor power", "11 kW"),
        ("design pressure", "10 bar"),
    ]
    assert facts[0].value == 11
    assert facts[0].unit == "kw"


def test_layout_table_state_resets_before_footer(tmp_path):
    path = tmp_path / "table-footer.pdf"
    make_positioned_pdf(
        path,
        [
            ["Parameter", "Unit", "Required", "Offered"],
            ["Motor power", "kW", ">= 10", "11"],
            ["Notes", "Values at rated duty", "", ""],
        ],
        [50, 250, 330, 430],
    )
    facts = parse_vendor_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [("motor power", "11 kW")]


def test_side_by_side_layout_pairs(tmp_path):
    path = tmp_path / "paired-layout.pdf"
    make_positioned_pdf(
        path,
        [
            ["Motor power", "11 kW", "Flow rate", "125 m3/h"],
            ["Design pressure", "10 bar", "Noise level", "68 dB"],
        ],
        [50, 200, 330, 470],
    )
    facts = parse_vendor_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [
        ("motor power", "11 kW"),
        ("flow rate", "125 m3/h"),
        ("design pressure", "10 bar"),
        ("noise level", "68 dB"),
    ]


def test_three_plus_column_non_table_line_is_not_misread_as_two_column_fact(tmp_path):
    path = tmp_path / "footer.pdf"
    make_positioned_pdf(
        path,
        [
            ["Document", "Rev", "Date"],
            ["Pump datasheet", "B", "2026-08-20"],
        ],
        [50, 250, 430],
    )
    assert parse_vendor_facts(path) == []


def test_layout_table_flows_into_compliance_engine(tmp_path):
    from bidlint.compare import compare
    from bidlint.models import Status

    specification = tmp_path / "spec-e2e.pdf"
    vendor = tmp_path / "vendor-e2e.pdf"
    make_pdf(
        specification,
        [
            "Motor power shall be minimum 10 kW",
            "Design pressure shall be minimum 10 bar",
        ],
    )
    make_positioned_pdf(
        vendor,
        [
            ["Parameter", "Unit", "Required", "Offered"],
            ["Motor power", "kW", ">= 10", "11"],
            ["Design pressure", "bar", ">= 10", "10"],
        ],
        [50, 250, 330, 430],
    )

    report = compare(
        parse_requirements(specification),
        parse_vendor_facts(vendor),
        specification.name,
        vendor.name,
    )
    assert [finding.status for finding in report.findings] == [Status.PASS, Status.PASS]
    assert report.compliance_score == 100.0
