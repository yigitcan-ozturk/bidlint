"""Synthetic XLSX-to-decision regression probes; not real supplier validation."""
from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

from bidlint.compare import compare
from bidlint.models import Status
from bidlint.specification_input import parse_specification_input
from bidlint.inputs import parse_vendor_input

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _xml(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _xlsx(path, rows):
    worksheet = ET.Element(f"{{{MAIN}}}worksheet")
    data = ET.SubElement(worksheet, f"{{{MAIN}}}sheetData")
    for row_num, values in enumerate(rows, 1):
        row = ET.SubElement(data, f"{{{MAIN}}}row", {"r": str(row_num)})
        for col_num, value in enumerate(values):
            cell = ET.SubElement(row, f"{{{MAIN}}}c", {
                "r": f"{chr(65 + col_num)}{row_num}", "t": "inlineStr"
            })
            inline = ET.SubElement(cell, f"{{{MAIN}}}is")
            ET.SubElement(inline, f"{{{MAIN}}}t").text = value
    workbook = ET.Element(f"{{{MAIN}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{MAIN}}}sheets")
    ET.SubElement(sheets, f"{{{MAIN}}}sheet", {
        "name": "Technical", "sheetId": "1", f"{{{REL}}}id": "rId1"
    })
    rels = ET.Element(f"{{{PKG}}}Relationships")
    ET.SubElement(rels, f"{{{PKG}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
        "Target": "/xl/worksheets/sheet1.xml",
    })
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(rels))
        archive.writestr("xl/worksheets/sheet1.xml", _xml(worksheet))


def test_synthetic_xlsx_requirement_and_vendor_e2e(tmp_path):
    spec = tmp_path / "spec.xlsx"
    vendor = tmp_path / "vendor.xlsx"
    _xlsx(spec, [["Requirement", "Specification"],
                 ["Motor power", "minimum 10 kW"],
                 ["Design pressure", "minimum 12 bar"]])
    _xlsx(vendor, [["Parameter", "Offered"],
                   ["Motor power", "11 kW"],
                   ["Design pressure", "10 bar"]])

    requirements = parse_specification_input(spec, xlsx_sheet="Technical")
    facts = parse_vendor_input(vendor, xlsx_sheet="Technical")
    assert len(requirements) == len(facts) == 2
    report = compare(requirements, facts, spec.name, vendor.name)
    assert [finding.status for finding in report.findings] == [Status.PASS, Status.DEVIATION]
    for finding in report.findings:
        assert finding.requirement.source is not None
        assert finding.vendor_fact is not None
        assert finding.vendor_fact.source is not None
        assert finding.requirement.source.document == spec.name
        assert finding.vendor_fact.source.document == vendor.name
