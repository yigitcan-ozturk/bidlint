from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bidlint.inputs import parse_vendor_input
from bidlint.xlsx_input import parse_xlsx_vendor_facts

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


@dataclass(frozen=True)
class Formula:
    expression: str


@dataclass(frozen=True)
class Shared:
    value: str


def _worksheet(rows: list[list[object]], *, merges: list[str] | None = None, shared: list[str] | None = None) -> bytes:
    root = ET.Element(_q("worksheet"))
    data = ET.SubElement(root, _q("sheetData"))
    for row_number, values in enumerate(rows, start=1):
        row = ET.SubElement(data, _q("row"), {"r": str(row_number)})
        for column, value in enumerate(values, start=1):
            if value is None or value == "":
                continue
            ref = f"{_column_name(column)}{row_number}"
            if isinstance(value, Formula):
                cell = ET.SubElement(row, _q("c"), {"r": ref})
                ET.SubElement(cell, _q("f")).text = value.expression
                ET.SubElement(cell, _q("v")).text = "0"
            elif isinstance(value, Shared):
                assert shared is not None
                shared.append(value.value)
                cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "s"})
                ET.SubElement(cell, _q("v")).text = str(len(shared) - 1)
            elif isinstance(value, bool):
                cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "b"})
                ET.SubElement(cell, _q("v")).text = "1" if value else "0"
            elif isinstance(value, (int, float)):
                cell = ET.SubElement(row, _q("c"), {"r": ref})
                ET.SubElement(cell, _q("v")).text = str(value)
            else:
                cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "inlineStr"})
                inline = ET.SubElement(cell, _q("is"))
                ET.SubElement(inline, _q("t")).text = str(value)
    if merges:
        merge_cells = ET.SubElement(root, _q("mergeCells"), {"count": str(len(merges))})
        for reference in merges:
            ET.SubElement(merge_cells, _q("mergeCell"), {"ref": reference})
    return _xml(root)


def _shared_strings(values: list[str]) -> bytes:
    root = ET.Element(_q("sst"), {"count": str(len(values)), "uniqueCount": str(len(values))})
    for value in values:
        item = ET.SubElement(root, _q("si"))
        ET.SubElement(item, _q("t")).text = value
    return _xml(root)


def _write_xlsx(
    path: Path,
    sheets: dict[str, list[list[object]]],
    *,
    hidden: set[str] | None = None,
    merges: dict[str, list[str]] | None = None,
    extras: dict[str, bytes] | None = None,
) -> None:
    hidden = hidden or set()
    merges = merges or {}
    shared_values: list[str] = []

    workbook = ET.Element(_q("workbook"))
    workbook_sheets = ET.SubElement(workbook, _q("sheets"))
    relationships = ET.Element(_pq("Relationships"))

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (name, rows) in enumerate(sheets.items(), start=1):
            attrs = {"name": name, "sheetId": str(index), _rq("id"): f"rId{index}"}
            if name in hidden:
                attrs["state"] = "hidden"
            ET.SubElement(workbook_sheets, _q("sheet"), attrs)
            ET.SubElement(
                relationships,
                _pq("Relationship"),
                {
                    "Id": f"rId{index}",
                    "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
                    "Target": f"/xl/worksheets/sheet{index}.xml",
                },
            )
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _worksheet(rows, merges=merges.get(name), shared=shared_values),
            )

        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(relationships))
        if shared_values:
            archive.writestr("xl/sharedStrings.xml", _shared_strings(shared_values))
        for name, payload in (extras or {}).items():
            archive.writestr(name, payload)


def test_parses_explicit_vendor_table_with_units_and_provenance(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(
        path,
        {
            "Offer": [
                ["Supplier technical offer"],
                ["Parameter", "Unit", "Offered", "Section"],
                ["Motor Power", "kW", 11, "Electrical"],
                ["Housing Material", "", "316L stainless steel", "Materials"],
                ["Noise Level", "dB", "68 dB", "Acoustics"],
            ]
        },
    )

    facts = parse_xlsx_vendor_facts(path)

    assert len(facts) == 3
    assert facts[0].parameter == "motor power"
    assert facts[0].raw_value == "11 kW"
    assert facts[0].value == 11
    assert facts[0].unit == "kw"
    assert facts[0].source.document == "vendor.xlsx"
    assert facts[0].source.line == 3
    assert facts[0].source.section == "XLSX:Offer/Electrical"

    assert facts[1].value is None
    assert facts[1].unit is None
    assert facts[1].raw_value == "316L stainless steel"

    assert facts[2].value == 68
    assert facts[2].unit == "db"
    assert facts[2].raw_value == "68 dB"


def test_shared_strings_are_supported(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(
        path,
        {
            "Offer": [
                [Shared("Parameter"), Shared("Offered")],
                [Shared("Motor Power"), Shared("11 kW")],
            ]
        },
    )

    facts = parse_xlsx_vendor_facts(path)
    assert facts[0].parameter == "motor power"
    assert facts[0].raw_value == "11 kW"


def test_parse_vendor_input_dispatches_xlsx(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(path, {"Offer": [["Parameter", "Unit", "Offered"], ["Motor Power", "kW", 11]]})

    facts = parse_vendor_input(path)
    assert facts[0].raw_value == "11 kW"

    with pytest.raises(ValueError, match="IFC selection options"):
        parse_vendor_input(path, ifc_class="IfcPump")


def test_requires_explicit_sheet_when_multiple_visible_sheets_exist(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(
        path,
        {
            "Offer A": [["Parameter", "Offered"], ["Motor Power", "10 kW"]],
            "Offer B": [["Parameter", "Offered"], ["Motor Power", "12 kW"]],
        },
    )

    with pytest.raises(ValueError, match="multiple visible worksheets"):
        parse_xlsx_vendor_facts(path)

    facts = parse_xlsx_vendor_facts(path, sheet="Offer B")
    assert facts[0].raw_value == "12 kW"


def test_rejects_hidden_sheet_as_evidence(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(
        path,
        {
            "Visible": [["Parameter", "Offered"], ["Motor Power", "10 kW"]],
            "Hidden": [["Parameter", "Offered"], ["Motor Power", "12 kW"]],
        },
        hidden={"Hidden"},
    )

    with pytest.raises(ValueError, match="hidden XLSX worksheets"):
        parse_xlsx_vendor_facts(path, sheet="Hidden")


def test_rejects_formula_cells(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(path, {"Offer": [["Parameter", "Offered"], ["Motor Power", Formula("10+1")]]})

    with pytest.raises(ValueError, match="formula cells are not accepted"):
        parse_xlsx_vendor_facts(path)


def test_rejects_merged_cells(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(
        path,
        {"Offer": [["Parameter", "Offered"], ["Motor Power", "11 kW"], ["note"]]},
        merges={"Offer": ["A3:B3"]},
    )

    with pytest.raises(ValueError, match="merged cells"):
        parse_xlsx_vendor_facts(path)


def test_rejects_macros_and_external_links(tmp_path):
    macro = tmp_path / "macro.xlsx"
    _write_xlsx(
        macro,
        {"Offer": [["Parameter", "Offered"], ["Motor Power", "11 kW"]]},
        extras={"xl/vbaProject.bin": b"not-a-real-macro"},
    )
    with pytest.raises(ValueError, match="must not contain macros"):
        parse_xlsx_vendor_facts(macro)

    linked = tmp_path / "linked.xlsx"
    _write_xlsx(
        linked,
        {"Offer": [["Parameter", "Offered"], ["Motor Power", "11 kW"]]},
        extras={"xl/externalLinks/externalLink1.xml": b"<externalLink/>"},
    )
    with pytest.raises(ValueError, match="must not contain external links"):
        parse_xlsx_vendor_facts(linked)


def test_rejects_ambiguous_or_incomplete_rows(tmp_path):
    duplicate_header = tmp_path / "duplicate-header.xlsx"
    _write_xlsx(
        duplicate_header,
        {"Offer": [["Parameter", "Property", "Offered"], ["Motor Power", "Motor Power", "11 kW"]]},
    )
    with pytest.raises(ValueError, match="exactly one parameter"):
        parse_xlsx_vendor_facts(duplicate_header)

    incomplete = tmp_path / "incomplete.xlsx"
    _write_xlsx(
        incomplete,
        {"Offer": [["Parameter", "Offered"], ["Motor Power", "11 kW"], ["Noise Level", ""]]},
    )
    with pytest.raises(ValueError, match="parameter but no offered value"):
        parse_xlsx_vendor_facts(incomplete)


def test_rejects_conflicting_embedded_and_explicit_units(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(path, {"Offer": [["Parameter", "Unit", "Offered"], ["Motor Power", "W", "11 kW"]]})

    with pytest.raises(ValueError, match="conflicting offered/unit values"):
        parse_xlsx_vendor_facts(path)


def test_boolean_offered_values_remain_qualitative(tmp_path):
    path = tmp_path / "vendor.xlsx"
    _write_xlsx(path, {"Offer": [["Parameter", "Offered"], ["Weatherproof", True]]})

    fact = parse_xlsx_vendor_facts(path)[0]
    assert fact.raw_value == "TRUE"
    assert fact.value is None
    assert fact.unit is None


def test_rejects_external_relationships_even_without_external_links_part(tmp_path):
    path = tmp_path / "hyperlink.xlsx"
    relationships = ET.Element(_pq("Relationships"))
    ET.SubElement(
        relationships,
        _pq("Relationship"),
        {
            "Id": "rId99",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
            "Target": "https://example.com/vendor-data",
            "TargetMode": "External",
        },
    )
    _write_xlsx(
        path,
        {"Offer": [["Parameter", "Offered"], ["Motor Power", "11 kW"]]},
        extras={"xl/worksheets/_rels/sheet1.xml.rels": _xml(relationships)},
    )

    with pytest.raises(ValueError, match="must not contain external relationships"):
        parse_xlsx_vendor_facts(path)
