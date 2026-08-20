from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from bidlint.xlsx_input import parse_xlsx_facts

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sanitized_vendor_workbooks.json"


def _column_name(index: int) -> str:
    parts: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        parts.append(chr(65 + remainder))
    return "".join(reversed(parts))


def _cell(reference: str, value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{reference}"><v>{value:g}</v></c>'
    return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _sheet_xml(rows: list[list[object | None]]) -> str:
    xml_rows: list[str] = []
    for row_number, values in enumerate(rows, start=1):
        cells = "".join(
            _cell(f"{_column_name(column)}{row_number}", value)
            for column, value in enumerate(values, start=1)
            if value is not None and value != ""
        )
        xml_rows.append(f'<row r="{row_number}">{cells}</row>')
    return f'<worksheet xmlns="{_MAIN_NS}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'


def _write_workbook(path: Path, sheets: list[dict]) -> None:
    workbook_sheets = "".join(
        f'<sheet name={quoteattr(sheet["name"])} sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, start=1)
    )
    relationships = "".join(
        f'<Relationship Id="rId{index}" Target="worksheets/sheet{index}.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        for index in range(1, len(sheets) + 1)
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{_MAIN_NS}" xmlns:r="{_REL_NS}"><sheets>{workbook_sheets}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{_PACKAGE_REL_NS}">{relationships}</Relationships>',
        )
        for index, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(sheet["rows"]))


def test_sanitized_vendor_workbook_fixtures_preserve_expected_facts(tmp_path):
    fixtures = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

    for fixture in fixtures:
        path = tmp_path / f'{fixture["name"]}.xlsx'
        _write_workbook(path, fixture["sheets"])

        facts = parse_xlsx_facts(path)
        observed = [
            [fact.parameter, fact.raw_value, fact.source.section, fact.source.line]
            for fact in facts
            if fact.source is not None
        ]
        assert observed == fixture["expected"], fixture["name"]
