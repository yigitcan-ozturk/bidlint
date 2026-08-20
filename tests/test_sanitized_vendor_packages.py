from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.document_policy import DocumentClass
from bidlint.vendor_package import parse_vendor_package

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sanitized_vendor_packages.json"
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("", _MAIN_NS)
ET.register_namespace("r", _REL_NS)


def _q(tag: str) -> str:
    return f"{{{_MAIN_NS}}}{tag}"


def _rq(tag: str) -> str:
    return f"{{{_REL_NS}}}{tag}"


def _pq(tag: str) -> str:
    return f"{{{_PACKAGE_REL_NS}}}{tag}"


def _xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _load_fixtures():
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _render_pdf(path: Path, rows: list[list[object]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    x_positions = (50, 250, 330, 430)
    headers = ("Parameter", "Unit", "Required", "Offered")
    y = 800
    for x, text in zip(x_positions, headers, strict=True):
        c.drawString(x, y, text)
    y -= 24
    for row in rows:
        for x, value in zip(x_positions, row, strict=True):
            c.drawString(x, y, str(value))
        y -= 24
    c.save()


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _worksheet(rows: list[list[object]]) -> bytes:
    root = ET.Element(_q("worksheet"))
    data = ET.SubElement(root, _q("sheetData"))
    for row_number, values in enumerate(rows, start=1):
        row = ET.SubElement(data, _q("row"), {"r": str(row_number)})
        for column, value in enumerate(values, start=1):
            if value is None or value == "":
                continue
            reference = f"{_column_name(column)}{row_number}"
            if isinstance(value, (int, float)):
                cell = ET.SubElement(row, _q("c"), {"r": reference})
                ET.SubElement(cell, _q("v")).text = str(value)
            else:
                cell = ET.SubElement(row, _q("c"), {"r": reference, "t": "inlineStr"})
                inline = ET.SubElement(cell, _q("is"))
                ET.SubElement(inline, _q("t")).text = str(value)
    return _xml(root)


def _write_xlsx(path: Path, rows: list[list[object]]) -> None:
    workbook = ET.Element(_q("workbook"))
    sheets = ET.SubElement(workbook, _q("sheets"))
    ET.SubElement(sheets, _q("sheet"), {"name": "Offer", "sheetId": "1", _rq("id"): "rId1"})

    relationships = ET.Element(_pq("Relationships"))
    ET.SubElement(
        relationships,
        _pq("Relationship"),
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": "/xl/worksheets/sheet1.xml",
        },
    )

    table = [["Parameter", "Unit", "Offered"], *rows]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(relationships))
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet(table))


def _render_package(root: Path, fixture: dict[str, object]) -> None:
    root.mkdir()
    for document in fixture["documents"]:
        path = root / document["name"]
        kind = document["type"]
        if kind == "pdf":
            _render_pdf(path, document["rows"])
        elif kind == "xlsx":
            _write_xlsx(path, document["rows"])
        elif kind == "text":
            path.write_text(document["content"], encoding="utf-8")
        else:
            raise AssertionError(f"unsupported fixture document type: {kind}")


@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda fixture: fixture["name"])
def test_sanitized_multi_document_packages(tmp_path, fixture) -> None:
    root = tmp_path / fixture["name"]
    _render_package(root, fixture)

    package = parse_vendor_package(
        root,
        aliases=fixture.get("aliases"),
        evidence_priority=tuple(fixture.get("evidence_priority", [])) or None,
    )

    expected = fixture["expected"]
    dispositions = Counter(entry.disposition.value for entry in package.evidence_audit)

    assert len(package.conflicts) == expected["conflicts"]
    assert dispositions == Counter(expected["dispositions"])

    if "selected_sources" in expected:
        selected_sources = {
            entry.fact.source.document
            for entry in package.evidence_audit
            if entry.disposition.value == "selected" and entry.fact.source is not None
        }
        assert selected_sources == set(expected["selected_sources"])

    if "ignored_documents" in expected:
        assert [path.name for path in package.ignored_documents] == expected["ignored_documents"]

    for name in expected.get("specification_documents", []):
        assert package.document_classes[name] is DocumentClass.SPECIFICATION


def test_sanitized_package_fixture_set_covers_v07_equipment_families() -> None:
    fixtures = _load_fixtures()
    assert {fixture["name"] for fixture in fixtures} == {
        "pump_package",
        "motor_package",
        "valve_package",
        "hvac_package",
        "electrical_package",
    }


def test_sanitized_package_fixtures_are_non_vendor_specific() -> None:
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
