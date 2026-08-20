import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.parse import parse_vendor_facts

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sanitized_vendor_layouts.json"


def _load_fixtures():
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _render_fixture(path: Path, pages):
    c = canvas.Canvas(str(path), pagesize=A4)
    for page_index, rows in enumerate(pages):
        y = 800
        for row in rows:
            for x, text in row:
                c.drawString(x, y, text)
            y -= 24
        if page_index + 1 < len(pages):
            c.showPage()
    c.save()


@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda fixture: fixture["name"])
def test_sanitized_vendor_layouts_preserve_expected_facts(tmp_path, fixture):
    path = tmp_path / f"{fixture['name']}.pdf"
    _render_fixture(path, fixture["pages"])

    facts = parse_vendor_facts(path)
    actual = [
        [
            fact.parameter,
            fact.raw_value,
            fact.source.page if fact.source else None,
        ]
        for fact in facts
    ]

    assert actual == fixture["expected"]


def test_sanitized_fixtures_are_explicitly_non_vendor_specific():
    serialized = _FIXTURE_PATH.read_text(encoding="utf-8").lower()
    forbidden_markers = {
        "abb",
        "grundfos",
        "siemens",
        "schneider",
        "danfoss",
        "kone",
    }
    assert not any(marker in serialized for marker in forbidden_markers)
