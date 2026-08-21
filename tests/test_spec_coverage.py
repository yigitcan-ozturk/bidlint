from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

from bidlint.spec_coverage import specification_coverage

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


def _write_xlsx(path, *, include_schedule: bool) -> None:
    rows = [
        ["Private technical schedule"],
        ["General Requirement", "Specification"],
        ["Material", "Grade 304 stainless steel"],
        ["Load Class", "A15"],
    ]
    if include_schedule:
        rows.extend([[], ["Item", "Length (mm)"], [1, 3000], [2, 2500]])

    worksheet = ET.Element(_q("worksheet"))
    data = ET.SubElement(worksheet, _q("sheetData"))
    for row_number, values in enumerate(rows, start=1):
        row = ET.SubElement(data, _q("row"), {"r": str(row_number)})
        for column, value in enumerate(values, start=1):
            if value in (None, ""):
                continue
            ref = f"{'AB'[column - 1]}{row_number}"
            if isinstance(value, (int, float)):
                cell = ET.SubElement(row, _q("c"), {"r": ref})
                ET.SubElement(cell, _q("v")).text = str(value)
            else:
                cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "inlineStr"})
                inline = ET.SubElement(cell, _q("is"))
                ET.SubElement(inline, _q("t")).text = str(value)

    workbook = ET.Element(_q("workbook"))
    sheets = ET.SubElement(workbook, _q("sheets"))
    ET.SubElement(sheets, _q("sheet"), {"name": "Schedule", "sheetId": "1", _rq("id"): "rId1"})
    rels = ET.Element(_pq("Relationships"))
    ET.SubElement(
        rels,
        _pq("Relationship"),
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": "/xl/worksheets/sheet1.xml",
        },
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", _xml(worksheet))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(rels))


def test_xlsx_coverage_reports_unscoped_rows_without_copying_cell_text(tmp_path):
    path = tmp_path / "specification.xlsx"
    _write_xlsx(path, include_schedule=True)

    coverage = specification_coverage(path)

    assert coverage == {
        "kind": "xlsx",
        "coverage_observable": True,
        "header_row": 2,
        "evaluated_requirement_row_count": 2,
        "first_evaluated_row": 3,
        "last_evaluated_row": 4,
        "unscoped_populated_row_count": 3,
        "first_unscoped_row": 6,
        "last_populated_row": 8,
        "manual_scope_review_required": True,
    }
    rendered = str(coverage)
    assert "Grade 304" not in rendered
    assert "3000" not in rendered


def test_xlsx_coverage_is_clear_when_requirement_block_exhausts_sheet(tmp_path):
    path = tmp_path / "specification.xlsx"
    _write_xlsx(path, include_schedule=False)

    coverage = specification_coverage(path)

    assert coverage["manual_scope_review_required"] is False
    assert coverage["unscoped_populated_row_count"] == 0
    assert coverage["first_unscoped_row"] is None


def test_pdf_coverage_does_not_claim_structured_observability(tmp_path):
    path = tmp_path / "specification.pdf"
    path.write_bytes(b"placeholder")

    coverage = specification_coverage(path)

    assert coverage == {
        "kind": "pdf",
        "coverage_observable": False,
        "manual_scope_review_required": False,
    }
