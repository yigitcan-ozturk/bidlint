from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from .models import SourceRef, VendorFact

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_PARAMETER_HEADERS = {"parameter", "property", "description", "technical parameter", "item"}
_OFFERED_HEADERS = {"offered", "offered value", "vendor value", "supplier value", "value"}
_UNIT_HEADERS = {"unit", "units"}
_SECTION_HEADERS = {"section", "category", "system"}
_NUMERIC_VALUE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/^\-²³]+)?\s*$")
_CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")
_MAX_ARCHIVE_ENTRIES = 10_000
_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_MAX_DATA_ROWS = 100_000
_MAX_COLUMNS = 256


def _q(tag: str) -> str:
    return f"{{{_MAIN_NS}}}{tag}"


def _rq(tag: str) -> str:
    return f"{{{_REL_NS}}}{tag}"


def _pq(tag: str) -> str:
    return f"{{{_PACKAGE_REL_NS}}}{tag}"


def _normalize_header(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    normalized = unit.strip().lower().replace("º", "°")
    return {
        "percent": "%",
        "percentage": "%",
        "degc": "°c",
        "c": "°c",
        "degrees": "°",
    }.get(normalized, normalized)


def _parse_numeric_value(raw_value: str) -> tuple[float | None, str | None]:
    match = _NUMERIC_VALUE.fullmatch(raw_value)
    if not match:
        return None, None
    return float(match.group(1)), _normalize_unit(match.group(2))


def _column_index(reference: str) -> int:
    match = _CELL_REF.fullmatch(reference)
    if not match:
        raise ValueError(f"unsupported XLSX cell reference: {reference}")
    letters = match.group(1)
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - 64)
    if index > _MAX_COLUMNS:
        raise ValueError("XLSX vendor input exceeds supported column limit")
    return index


def _resolve_workbook_target(target: str) -> str:
    raw = target.strip()
    if not raw:
        raise ValueError("empty workbook relationship target")
    normalized = PurePosixPath(raw.lstrip("/")) if raw.startswith("/") else PurePosixPath("xl") / raw
    parts: list[str] = []
    for part in normalized.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("invalid workbook relationship target")
            parts.pop()
        else:
            parts.append(part)
    resolved = "/".join(parts)
    if not resolved.startswith("xl/"):
        raise ValueError("worksheet relationship escapes workbook package")
    return resolved


@dataclass(frozen=True, slots=True)
class _Sheet:
    name: str
    state: str
    path: str


def _validate_archive(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > _MAX_ARCHIVE_ENTRIES:
        raise ValueError("XLSX archive contains too many entries")
    names_list = [info.filename for info in infos]
    if len(names_list) != len(set(names_list)):
        raise ValueError("XLSX archive contains duplicate package entries")
    total = sum(info.file_size for info in infos)
    if total > _MAX_UNCOMPRESSED_BYTES:
        raise ValueError("XLSX archive is too large after decompression")
    names = set(names_list)
    if "xl/vbaProject.bin" in names or any(name.startswith("xl/macrosheets/") for name in names):
        raise ValueError("XLSX vendor input must not contain macros")
    if any(name.startswith("xl/externalLinks/") for name in names):
        raise ValueError("XLSX vendor input must not contain external links")
    for name in names:
        if not name.endswith(".rels"):
            continue
        try:
            relationships = ET.fromstring(archive.read(name))
        except ET.ParseError as exc:
            raise ValueError(f"invalid XLSX relationship package part: {name}") from exc
        if any(rel.attrib.get("TargetMode") == "External" for rel in relationships.findall(_pq("Relationship"))):
            raise ValueError("XLSX vendor input must not contain external relationships")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(_q("si")):
        strings.append("".join(node.text or "" for node in item.iter(_q("t"))))
    return strings


def _workbook_sheets(archive: zipfile.ZipFile) -> list[_Sheet]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(_pq("Relationship"))
        if rel.attrib.get("Type", "").endswith("/worksheet")
    }
    sheets: list[_Sheet] = []
    for sheet in workbook.findall(f"{_q('sheets')}/{_q('sheet')}"):
        rel_id = sheet.attrib.get(_rq("id"))
        if not rel_id or rel_id not in targets:
            raise ValueError(f"worksheet relationship missing for {sheet.attrib.get('name', '<unnamed>')}")
        sheets.append(
            _Sheet(
                name=sheet.attrib["name"],
                state=sheet.attrib.get("state", "visible"),
                path=_resolve_workbook_target(targets[rel_id]),
            )
        )
    if not sheets:
        raise ValueError("XLSX vendor input contains no worksheets")
    return sheets


def _select_sheet(sheets: list[_Sheet], requested: str | None) -> _Sheet:
    if requested is not None:
        matches = [sheet for sheet in sheets if sheet.name == requested]
        if not matches:
            raise ValueError(f"XLSX worksheet not found: {requested}")
        selected = matches[0]
        if selected.state != "visible":
            raise ValueError("hidden XLSX worksheets are not accepted as vendor evidence")
        return selected

    visible = [sheet for sheet in sheets if sheet.state == "visible"]
    if len(visible) == 1:
        return visible[0]
    if not visible:
        raise ValueError("XLSX vendor input contains no visible worksheet")
    names = ", ".join(sheet.name for sheet in visible)
    raise ValueError(f"XLSX vendor input has multiple visible worksheets ({names}); use --xlsx-sheet")


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    if cell.find(_q("f")) is not None:
        raise ValueError(f"formula cells are not accepted as vendor evidence ({cell.attrib.get('r', '?')})")

    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(_q("is"))
        return "" if inline is None else "".join(node.text or "" for node in inline.iter(_q("t"))).strip()

    value = cell.find(_q("v"))
    raw = "" if value is None or value.text is None else value.text.strip()
    if cell_type == "s":
        try:
            return shared[int(raw)].strip()
        except (ValueError, IndexError) as exc:
            raise ValueError(f"invalid shared-string index in {cell.attrib.get('r', '?')}") from exc
    if cell_type == "b":
        if raw not in {"0", "1"}:
            raise ValueError(f"invalid XLSX boolean value at {cell.attrib.get('r', '?')}")
        return "TRUE" if raw == "1" else "FALSE"
    if cell_type in {None, "n", "str"}:
        return raw
    if cell_type in {"e", "d"}:
        raise ValueError(f"unsupported XLSX cell type {cell_type!r} at {cell.attrib.get('r', '?')}")
    raise ValueError(f"unsupported XLSX cell type {cell_type!r} at {cell.attrib.get('r', '?')}")


def _rows(sheet_root: ET.Element, shared: list[str]) -> list[tuple[int, dict[int, str]]]:
    if sheet_root.find(_q("mergeCells")) is not None:
        raise ValueError("merged cells are not accepted in XLSX vendor input")

    rows: list[tuple[int, dict[int, str]]] = []
    for row in sheet_root.findall(f"{_q('sheetData')}/{_q('row')}"):
        try:
            row_number = int(row.attrib["r"])
        except (KeyError, ValueError) as exc:
            raise ValueError("XLSX worksheet row is missing a valid row number") from exc
        values: dict[int, str] = {}
        for cell in row.findall(_q("c")):
            reference = cell.attrib.get("r")
            if not reference:
                raise ValueError(f"XLSX row {row_number} contains a cell without a reference")
            column = _column_index(reference)
            text = _cell_text(cell, shared)
            if text:
                values[column] = text
        if values:
            rows.append((row_number, values))
    return rows


def _header_map(rows: list[tuple[int, dict[int, str]]]) -> tuple[int, dict[str, int]]:
    for row_number, values in rows[:20]:
        normalized = {column: _normalize_header(value) for column, value in values.items()}
        parameter_cols = [column for column, value in normalized.items() if value in _PARAMETER_HEADERS]
        offered_cols = [column for column, value in normalized.items() if value in _OFFERED_HEADERS]
        if not parameter_cols or not offered_cols:
            continue
        if len(parameter_cols) != 1 or len(offered_cols) != 1:
            raise ValueError("XLSX header must contain exactly one parameter column and one offered-value column")

        mapping = {"parameter": parameter_cols[0], "offered": offered_cols[0]}
        unit_cols = [column for column, value in normalized.items() if value in _UNIT_HEADERS]
        section_cols = [column for column, value in normalized.items() if value in _SECTION_HEADERS]
        if len(unit_cols) > 1 or len(section_cols) > 1:
            raise ValueError("XLSX header contains duplicate optional columns")
        if unit_cols:
            mapping["unit"] = unit_cols[0]
        if section_cols:
            mapping["section"] = section_cols[0]
        return row_number, mapping
    raise ValueError(
        "XLSX vendor input requires an explicit parameter/offered header row within the first 20 populated rows"
    )


def parse_xlsx_vendor_facts(path: str | Path, *, sheet: str | None = None) -> list[VendorFact]:
    """Parse an explicitly tabulated XLSX vendor offer into deterministic VendorFact records.

    The selected worksheet must expose one parameter column and one offered-value
    column. Optional unit and section columns are preserved. Formulas, macros,
    external links, merged cells and hidden evidence sheets are rejected rather
    than evaluated or guessed.
    """
    file_path = Path(path)
    if file_path.suffix.lower() != ".xlsx":
        raise ValueError("XLSX vendor input must end in .xlsx")

    try:
        archive = zipfile.ZipFile(file_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("invalid XLSX vendor input") from exc

    with archive:
        _validate_archive(archive)
        required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
        missing = required.difference(archive.namelist())
        if missing:
            raise ValueError("invalid XLSX workbook package")
        shared = _shared_strings(archive)
        selected = _select_sheet(_workbook_sheets(archive), sheet)
        if selected.path not in archive.namelist():
            raise ValueError(f"worksheet package part missing for {selected.name}")
        root = ET.fromstring(archive.read(selected.path))
        rows = _rows(root, shared)

    header_row, columns = _header_map(rows)
    facts: list[VendorFact] = []
    data_rows = [(row_number, values) for row_number, values in rows if row_number > header_row]
    if len(data_rows) > _MAX_DATA_ROWS:
        raise ValueError("XLSX vendor input contains too many data rows")

    for row_number, values in data_rows:
        parameter = values.get(columns["parameter"], "").strip()
        offered = values.get(columns["offered"], "").strip()
        unit_text = values.get(columns.get("unit", -1), "").strip() if "unit" in columns else ""
        section = values.get(columns.get("section", -1), "").strip() if "section" in columns else ""

        if not parameter and not offered:
            continue
        if not parameter:
            raise ValueError(f"XLSX row {row_number} has an offered value but no parameter")
        if not offered:
            raise ValueError(f"XLSX row {row_number} has a parameter but no offered value")

        value, embedded_unit = _parse_numeric_value(offered)
        explicit_unit = _normalize_unit(unit_text) if unit_text else None
        if embedded_unit and explicit_unit and embedded_unit != explicit_unit:
            raise ValueError(
                f"XLSX row {row_number} contains conflicting offered/unit values: {embedded_unit} vs {explicit_unit}"
            )
        unit = embedded_unit or explicit_unit
        raw_value = offered
        if value is not None and embedded_unit is None and explicit_unit:
            raw_value = f"{offered} {unit_text.strip()}"

        facts.append(
            VendorFact(
                parameter=parameter.lower(),
                raw_value=raw_value,
                value=value,
                unit=unit,
                source=SourceRef(
                    document=file_path.name,
                    line=row_number,
                    section=f"XLSX:{selected.name}" + (f"/{section}" if section else ""),
                ),
            )
        )

    if not facts:
        raise ValueError("XLSX vendor input contains no populated vendor facts")
    return facts
