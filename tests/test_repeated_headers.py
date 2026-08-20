from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.parse import parse_vendor_facts


def make_positioned_pdf(path: Path, rows: list[list[str]], xs: list[int]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for row in rows:
        for x, text in zip(xs, row, strict=True):
            c.drawString(x, y, text)
        y -= 24
    c.save()


def make_sparse_positioned_pdf(path: Path, rows: list[list[tuple[int, str]]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for row in rows:
        for x, text in row:
            c.drawString(x, y, text)
        y -= 24
    c.save()


def test_repeated_explicit_header_groups_parse_two_facts_per_row(tmp_path):
    path = tmp_path / "repeated-groups.pdf"
    make_positioned_pdf(
        path,
        [
            ["Parameter", "Unit", "Offered", "Parameter", "Unit", "Offered"],
            ["Motor power", "kW", "11", "Flow rate", "m3/h", "125"],
            ["Design pressure", "bar", "10", "Noise level", "dB", "68"],
        ],
        [40, 155, 225, 310, 430, 510],
    )

    facts = parse_vendor_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [
        ("motor power", "11 kW"),
        ("flow rate", "125 m3/h"),
        ("design pressure", "10 bar"),
        ("noise level", "68 dB"),
    ]


def test_single_group_prefers_nearest_parameter_like_header_before_offered(tmp_path):
    path = tmp_path / "item-description.pdf"
    make_positioned_pdf(
        path,
        [
            ["Item", "Description", "Unit", "Offered"],
            ["1", "Motor power", "kW", "11"],
        ],
        [40, 120, 330, 430],
    )

    facts = parse_vendor_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [("motor power", "11 kW")]


def test_incomplete_repeated_group_row_is_skipped_as_a_whole(tmp_path):
    path = tmp_path / "incomplete-repeated.pdf"
    make_sparse_positioned_pdf(
        path,
        [
            [(40, "Parameter"), (155, "Unit"), (225, "Offered"), (310, "Parameter"), (430, "Unit"), (510, "Offered")],
            [(40, "Motor power"), (155, "kW"), (225, "11"), (310, "Flow rate"), (430, "m3/h")],
        ],
    )

    assert parse_vendor_facts(path) == []
