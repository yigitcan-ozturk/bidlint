from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.cli import main
from bidlint.inputs import parse_vendor_input
from bidlint.models import SourceRef
from bidlint.xlsx_input import parse_xlsx_facts

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _write_workbook(path: Path, sheet_xml: str, *, shared_strings: list[str] | None = None) -> None:
    workbook = (
        f'<workbook xmlns="{_MAIN_NS}" xmlns:r="{_REL_NS}">'
        '<sheets><sheet name="Vendor Data" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    relationships = (
        f'<Relationships xmlns="{_PACKAGE_REL_NS}">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        if shared_strings is not None:
            items = "".join(f"<si><t>{value}</t></si>" for value in shared_strings)
            archive.writestr(
                "xl/sharedStrings.xml",
                f'<sst xmlns="{_MAIN_NS}" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
                f"{items}</sst>",
            )


def _make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def test_xlsx_vendor_table_preserves_units_qualitative_values_and_provenance(tmp_path):
    path = tmp_path / "vendor.xlsx"
    strings = ["Parameter", "Unit", "Offered", "Motor power", "kW", "Housing", "316L stainless steel"]
    sheet = f'''<worksheet xmlns="{_MAIN_NS}"><sheetData>
      <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>
      <row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="s"><v>4</v></c><c r="C2"><v>11</v></c></row>
      <row r="3"><c r="A3" t="s"><v>5</v></c><c r="C3" t="s"><v>6</v></c></row>
    </sheetData></worksheet>'''
    _write_workbook(path, sheet, shared_strings=strings)

    facts = parse_xlsx_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [
        ("motor power", "11 kW"),
        ("housing", "316L stainless steel"),
    ]
    assert facts[0].value == 11
    assert facts[0].unit == "kw"
    assert facts[1].value is None
    assert facts[1].unit is None
    assert facts[0].source == SourceRef(document="vendor.xlsx", line=2, section="Vendor Data")


def test_xlsx_repeated_explicit_header_groups_are_parsed_without_positional_guessing(tmp_path):
    path = tmp_path / "vendor.xlsx"
    sheet = f'''<worksheet xmlns="{_MAIN_NS}"><sheetData>
      <row r="1">
        <c r="A1" t="inlineStr"><is><t>Parameter</t></is></c>
        <c r="B1" t="inlineStr"><is><t>Offered</t></is></c>
        <c r="D1" t="inlineStr"><is><t>Property</t></is></c>
        <c r="E1" t="inlineStr"><is><t>Vendor Value</t></is></c>
      </row>
      <row r="2">
        <c r="A2" t="inlineStr"><is><t>Motor power</t></is></c><c r="B2" t="inlineStr"><is><t>11 kW</t></is></c>
        <c r="D2" t="inlineStr"><is><t>Design pressure</t></is></c><c r="E2" t="inlineStr"><is><t>10 bar</t></is></c>
      </row>
    </sheetData></worksheet>'''
    _write_workbook(path, sheet)

    facts = parse_xlsx_facts(path)
    assert [(fact.parameter, fact.raw_value) for fact in facts] == [
        ("motor power", "11 kW"),
        ("design pressure", "10 bar"),
    ]


def test_xlsx_formula_cells_are_rejected_in_deterministic_input(tmp_path):
    path = tmp_path / "vendor.xlsx"
    sheet = f'''<worksheet xmlns="{_MAIN_NS}"><sheetData>
      <row r="1"><c r="A1" t="inlineStr"><is><t>Parameter</t></is></c><c r="B1" t="inlineStr"><is><t>Offered</t></is></c></row>
      <row r="2"><c r="A2" t="inlineStr"><is><t>Motor power</t></is></c><c r="B2"><f>10+1</f><v>11</v></c></row>
    </sheetData></worksheet>'''
    _write_workbook(path, sheet)

    with pytest.raises(ValueError, match="formula cells are not supported"):
        parse_xlsx_facts(path)


def test_cli_compares_specification_pdf_with_xlsx_vendor(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.xlsx"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    sheet = f'''<worksheet xmlns="{_MAIN_NS}"><sheetData>
      <row r="1"><c r="A1" t="inlineStr"><is><t>Parameter</t></is></c><c r="B1" t="inlineStr"><is><t>Offered</t></is></c></row>
      <row r="2"><c r="A2" t="inlineStr"><is><t>Motor power</t></is></c><c r="B2" t="inlineStr"><is><t>11 kW</t></is></c></row>
    </sheetData></worksheet>'''
    _write_workbook(vendor, sheet)

    facts = parse_vendor_input(vendor)
    assert facts[0].parameter == "motor power"

    exit_code = main(["compare", str(specification), str(vendor), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["vendor"] == "vendor.xlsx"
    assert payload["compliance_score"] == 100.0
    assert payload["findings"][0]["status"] == "PASS"


def test_vendor_input_dispatch_rejects_ifc_selection_for_xlsx(tmp_path):
    path = tmp_path / "vendor.xlsx"
    sheet = f'''<worksheet xmlns="{_MAIN_NS}"><sheetData>
      <row r="1"><c r="A1" t="inlineStr"><is><t>Parameter</t></is></c><c r="B1" t="inlineStr"><is><t>Offered</t></is></c></row>
    </sheetData></worksheet>'''
    _write_workbook(path, sheet)

    with pytest.raises(ValueError, match="only be used with .ifc"):
        parse_vendor_input(path, ifc_class="IfcPump")
