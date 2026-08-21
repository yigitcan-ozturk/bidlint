from __future__ import annotations

import json
import zipfile

from bidlint.sanitize_scan import scan_file


def test_scan_blocks_currency_number_format_even_when_cell_value_has_no_currency_text(tmp_path):
    workbook = tmp_path / "specification.xlsx"
    styles = """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1">
    <numFmt numFmtId="164" formatCode="£#,##0.00"/>
  </numFmts>
  <cellXfs count="2">
    <xf numFmtId="0"/>
    <xf numFmtId="164" applyNumberFormat="1"/>
  </cellXfs>
</styleSheet>
"""
    worksheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" s="1"><v>125.00</v></c></row>
  </sheetData>
</worksheet>
"""
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)

    findings = scan_file(workbook)

    blockers = [finding for finding in findings if finding.severity == "BLOCK"]
    assert any(finding.category == "xlsx-currency-formatted-cells" and finding.count == 1 for finding in blockers)
    rendered = json.dumps([finding.to_dict() for finding in findings])
    assert "125.00" not in rendered


def test_scan_blocks_procurement_rate_and_total_column_labels(tmp_path):
    workbook = tmp_path / "specification.xlsx"
    shared_strings = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3">
  <si><t>Unit Rate</t></si>
  <si><t>Line Total</t></si>
  <si><t>Technical Description</t></si>
</sst>
"""
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", shared_strings)

    findings = scan_file(workbook)

    commercial = [
        finding for finding in findings if finding.severity == "BLOCK" and finding.category == "commercial-terms"
    ]
    assert commercial
    assert sum(finding.count for finding in commercial) >= 2


def test_technical_flow_rate_label_is_not_mistaken_for_commercial_unit_rate(tmp_path):
    workbook = tmp_path / "technical.xlsx"
    shared_strings = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">
  <si><t>Flow Rate</t></si>
</sst>
"""
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", shared_strings)

    findings = scan_file(workbook)

    assert not any(finding.category == "commercial-terms" for finding in findings)
