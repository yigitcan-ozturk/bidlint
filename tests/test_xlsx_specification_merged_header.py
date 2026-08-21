from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

from bidlint.xlsx_spec import parse_xlsx_requirements

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


def _inline(row, ref: str, value: str) -> None:
    cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "inlineStr"})
    inline = ET.SubElement(cell, _q("is"))
    ET.SubElement(inline, _q("t")).text = value


def test_presentation_merge_does_not_block_explicit_requirement_block(tmp_path):
    path = tmp_path / "specification.xlsx"
    worksheet = ET.Element(_q("worksheet"))
    data = ET.SubElement(worksheet, _q("sheetData"))
    row1 = ET.SubElement(data, _q("row"), {"r": "1"})
    _inline(row1, "A1", "Private technical schedule")
    row2 = ET.SubElement(data, _q("row"), {"r": "2"})
    _inline(row2, "A2", "General Requirement")
    _inline(row2, "B2", "Specification")
    row3 = ET.SubElement(data, _q("row"), {"r": "3"})
    _inline(row3, "A3", "Material")
    _inline(row3, "B3", "Grade 304 stainless steel")
    merges = ET.SubElement(worksheet, _q("mergeCells"), {"count": "1"})
    ET.SubElement(merges, _q("mergeCell"), {"ref": "A1:F1"})

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

    requirements = parse_xlsx_requirements(path)
    assert len(requirements) == 1
    assert requirements[0].parameter == "material"
    assert requirements[0].operator is None
