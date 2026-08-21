from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.pilot import build_bidlint_args, load_manifest, run_pilot

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


def _write_xlsx(path: Path) -> None:
    sheets = {
        "Channel Schedule": [
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
        ],
        "Summary": [["Metric", "Value"], ["Schedule line items", 1]],
    }
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


def _make_vendor_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    lines = [
        "Material: Grade 304 stainless steel",
        "Load Class: A15",
        "Grating: Plain ladder grating",
        "Outlet: DN110 / KV110 vertical outlet",
        "Drawings: Fabrication and approval drawings to be developed",
        "Equivalents: Technically compliant equivalent product",
    ]
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def test_xlsx_specification_runs_through_repeatable_pilot_path(tmp_path):
    specification = tmp_path / "specification.xlsx"
    vendor = tmp_path / "vendor.pdf"
    manifest_path = tmp_path / "pilot.json"
    _write_xlsx(specification)
    _make_vendor_pdf(vendor)
    payload = {
        "pilot_id": "external-derived-xlsx-001",
        "specification": specification.name,
        "vendors": [vendor.name],
        "repeats": 2,
        "options": {
            "threshold": 0.52,
            "spec_xlsx_sheet": "Channel Schedule",
        },
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest, loaded = load_manifest(manifest_path)
    args = build_bidlint_args(manifest)
    result = run_pilot(manifest, loaded)

    assert "--spec-xlsx-sheet" in args
    assert args[args.index("--spec-xlsx-sheet") + 1] == "Channel Schedule"
    assert result["passed"] is True
    assert result["deterministic"] is True
    assert result["conformant"] is True
    assert result["evaluated_requirement_count"] == 6
    assert result["report_count"] == 1
    assert len(set(result["run_digests_sha256"])) == 1
