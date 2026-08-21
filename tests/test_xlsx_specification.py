from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bidlint.specification_input import parse_specification_input
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
            ref = f"{_column_name(column)}{row_number}"
            if isinstance(value, (int, float)):
                cell = ET.SubElement(row, _q("c"), {"r": ref})
                ET.SubElement(cell, _q("v")).text = str(value)
            else:
                cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "inlineStr"})
                inline = ET.SubElement(cell, _q("is"))
                ET.SubElement(inline, _q("t")).text = str(value)
    return _xml(root)


def _write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> None:
    workbook = ET.Element(_q("workbook"))
    workbook_sheets = ET.SubElement(workbook, _q("sheets"))
    relationships = ET.Element(_pq("Relationships"))

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (name, rows) in enumerate(sheets.items(), start=1):
            ET.SubElement(
                workbook_sheets,
                _q("sheet"),
                {"name": name, "sheetId": str(index), _rq("id"): f"rId{index}"},
            )
            ET.SubElement(
                relationships,
                _pq("Relationship"),
                {
                    "Id": f"rId{index}",
                    "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
                    "Target": f"/xl/worksheets/sheet{index}.xml",
                },
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet(rows))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(relationships))


def _drainage_schedule() -> list[list[object]]:
    return [
        ["Private technical schedule"],
        ["General Requirement", "Specification"],
        ["Material", "Grade 304 stainless steel, BS EN 10088"],
        ["Load Class", "A15"],
        ["Grating", "Plain ladder grating"],
        ["Outlet", "DN110 / KV110 vertical outlet"],
        ["Drawings", "Supplier to develop fabrication and approval drawings"],
        ["Equivalents", "Technically compliant equivalent products are acceptable"],
        [],
        ["Item", "Channel Reference", "Length (mm)", "Nominal Width (mm)", "Channel Depth (mm)"],
        [1, "TYPE-1", 3000, 150, 65],
    ]


def test_parses_contiguous_general_requirement_block_and_stops_before_item_schedule(tmp_path):
    path = tmp_path / "specification.xlsx"
    _write_xlsx(path, {"Channel Schedule": _drainage_schedule(), "Summary": [["Metric", "Value"], ["Items", 1]]})

    requirements = parse_xlsx_requirements(path, sheet="Channel Schedule")

    assert [item.parameter for item in requirements] == [
        "material",
        "load class",
        "grating",
        "outlet",
        "drawings",
        "equivalents",
    ]
    assert len(requirements) == 6
    assert all(item.operator is None for item in requirements)
    assert requirements[0].source.document == "specification.xlsx"
    assert requirements[0].source.line == 3
    assert requirements[0].source.section == "XLSX:Channel Schedule"


def test_scalar_requirement_can_remain_deterministic(tmp_path):
    path = tmp_path / "specification.xlsx"
    _write_xlsx(
        path,
        {
            "Requirements": [
                ["Requirement", "Specification"],
                ["Channel thickness", "minimum 1.5 mm"],
            ]
        },
    )

    requirement = parse_xlsx_requirements(path)[0]
    assert requirement.parameter == "channel thickness"
    assert requirement.operator == ">="
    assert requirement.value == 1.5
    assert requirement.unit == "mm"


def test_multiple_visible_sheets_require_explicit_specification_selector(tmp_path):
    path = tmp_path / "specification.xlsx"
    _write_xlsx(path, {"Channel Schedule": _drainage_schedule(), "Summary": [["Metric", "Value"], ["Items", 1]]})

    with pytest.raises(ValueError, match="multiple visible worksheets"):
        parse_xlsx_requirements(path)


def test_specification_dispatch_accepts_xlsx_and_rejects_selector_for_pdf(tmp_path):
    path = tmp_path / "specification.xlsx"
    _write_xlsx(path, {"Channel Schedule": _drainage_schedule()})
    assert len(parse_specification_input(path)) == 6

    with pytest.raises(ValueError, match="spec-xlsx-sheet"):
        parse_specification_input(tmp_path / "specification.pdf", xlsx_sheet="Channel Schedule")
