from __future__ import annotations

import json
import zipfile
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.cli import main

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


def _write_spec(path) -> None:
    rows = [
        ["Private technical schedule"],
        ["General Requirement", "Specification"],
        ["Material", "Grade 304 stainless steel"],
        ["Load Class", "A15"],
    ]
    worksheet = ET.Element(_q("worksheet"))
    data = ET.SubElement(worksheet, _q("sheetData"))
    for row_number, values in enumerate(rows, start=1):
        row = ET.SubElement(data, _q("row"), {"r": str(row_number)})
        for column, value in enumerate(values, start=1):
            if not value:
                continue
            reference = f"{'AB'[column - 1]}{row_number}"
            cell = ET.SubElement(row, _q("c"), {"r": reference, "t": "inlineStr"})
            inline = ET.SubElement(cell, _q("is"))
            ET.SubElement(inline, _q("t")).text = value

    workbook = ET.Element(_q("workbook"))
    sheets = ET.SubElement(workbook, _q("sheets"))
    ET.SubElement(sheets, _q("sheet"), {"name": "Channel Schedule", "sheetId": "1", _rq("id"): "rId1"})
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


def _write_vendor(path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(50, 800, "Material: Grade 304 stainless steel")
    pdf.drawString(50, 778, "Load Class: A15")
    pdf.save()


def test_compare_cli_accepts_xlsx_specification(tmp_path, capsys):
    specification = tmp_path / "specification.xlsx"
    vendor = tmp_path / "vendor.pdf"
    _write_spec(specification)
    _write_vendor(vendor)

    assert main(
        [
            "compare",
            str(specification),
            str(vendor),
            "--spec-xlsx-sheet",
            "Channel Schedule",
            "--json",
        ]
    ) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["specification"] == "specification.xlsx"
    assert report["counts"]["REVIEW"] == 2
    assert len(report["findings"]) == 2
