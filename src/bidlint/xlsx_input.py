from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import SourceRef, VendorFact
from .parse import _looks_like_label, _parse_numeric_value

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF = re.compile(r"^([A-Z]+)([1-9]\d*)$")
_PARAMETER_HEADERS = {"parameter", "property", "description", "technical parameter", "item"}
_UNIT_HEADERS = {"unit", "units"}
_OFFERED_HEADERS = {"offered", "offered value", "vendor value", "supplier value", "value"}
_TABLE_TERMINATORS = {"note", "notes", "remark", "remarks", "general notes"}
_MAX_ARCHIVE_ENTRIES = 4096
_MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
_MAX_XML_BYTES = 32 * 1024 * 1024
_MAX_SHEETS = 128


def _q(tag: str) -> str:
    return f"{{{_MAIN_NS}}}{tag}"


def _normalize_header(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


def _column_index(reference: str) -> int:
    match = _CELL_REF.fullmatch(reference.upper())
    if not match:
        raise ValueError(f"invalid XLSX cell reference: {reference}")
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - 64)
    return index - 1


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise ValueError(f"XLSX package is missing {name}") from exc
    if info.file_size > _MAX_XML_BYTES:
        raise ValueError(f"XLSX member is too large: {name}")
    return archive.read(info)


def _validate_archive(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > _MAX_ARCHIVE_ENTRIES:
        raise ValueError("XLSX package has too many archive entries")
    if sum(info.file_size for info in infos) > _MAX_ARCHIVE_BYTES:
        raise ValueError("XLSX package is too large")


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    if cell.find(_q("f")) is not None:
        raise ValueError("formula cells are not supported in deterministic XLSX vendor input")

    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(f".//{_q('t')}"))

    raw = cell.find(_q("v"))
    value = raw.text if raw is not None and raw.text is not None else ""
    if cell_type == "s":
        try:
            index = int(value)
            return shared_strings[index]
        except (ValueError, IndexError) as exc:
            raise ValueError("invalid XLSX shared-string reference") from exc
    if cell_type == "b":
        return "true" if value == "1" else "false" if value == "0" else value
    return value


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(_read_member(archive, "xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.findall(f".//{_q('t')}"))
        for item in root.findall(_q("si"))
    ]


def _worksheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(_read_member(archive, "xl/workbook.xml"))
    rel_root = ET.fromstring(_read_member(archive, "xl/_rels/workbook.xml.rels"))
    relationships: dict[str, str] = {}
    for relationship in rel_root.findall(f"{{{_PACKAGE_REL_NS}}}Relationship"):
        if relationship.attrib.get("TargetMode") == "External":
            continue
        rel_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if rel_id and target:
            relationships[rel_id] = target

    sheets = workbook.findall(f"{_q('sheets')}/{_q('sheet')}")
    if len(sheets) > _MAX_SHEETS:
        raise ValueError("XLSX workbook has too many sheets")

    result: list[tuple[str, str]] = []
    for sheet in sheets:
        name = sheet.attrib.get("name", "").strip()
        rel_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
        if not name or not rel_id or rel_id not in relationships:
            raise ValueError("XLSX workbook contains an unresolved worksheet")
        target = relationships[rel_id].lstrip("/")
        path = posixpath.normpath(posixpath.join("xl", target))
        if path.startswith("../") or not path.startswith("xl/"):
            raise ValueError("XLSX worksheet target escapes the package")
        if path not in archive.namelist():
            raise ValueError(f"XLSX package is missing worksheet for {name}")
        result.append((name, path))
    return result


def _sheet_rows(xml_bytes: bytes, shared_strings: list[str]) -> list[tuple[int, dict[int, str]]]:
    root = ET.fromstring(xml_bytes)
    rows: list[tuple[int, dict[int, str]]] = []
    fallback_row = 0
    for row in root.findall(f".//{_q('sheetData')}/{_q('row')}"):
        fallback_row += 1
        row_number = int(row.attrib.get("r", fallback_row))
        cells: dict[int, str] = {}
        fallback_column = 0
        for cell in row.findall(_q("c")):
            reference = cell.attrib.get("r")
            if reference:
                column = _column_index(reference)
            else:
                column = fallback_column
            fallback_column = column + 1
            value = _cell_text(cell, shared_strings).strip()
            if value:
                cells[column] = value
        rows.append((row_number, cells))
    return rows


def _header_groups(cells: dict[int, str]) -> tuple[tuple[int, int | None, int], ...]:
    normalized = {column: _normalize_header(value) for column, value in cells.items()}
    offered_columns = [column for column in sorted(normalized) if normalized[column] in _OFFERED_HEADERS]
    groups: list[tuple[int, int | None, int]] = []
    lower_bound = -1
    for offered_column in offered_columns:
        parameter_columns = [
            column
            for column in sorted(normalized)
            if lower_bound < column < offered_column and normalized[column] in _PARAMETER_HEADERS
        ]
        if not parameter_columns:
            continue
        parameter_column = parameter_columns[-1]
        unit_column = next(
            (
                column
                for column in sorted(normalized)
                if parameter_column < column < offered_column and normalized[column] in _UNIT_HEADERS
            ),
            None,
        )
        groups.append((parameter_column, unit_column, offered_column))
        lower_bound = offered_column
    return tuple(groups)


def _row_facts(
    path: Path,
    sheet_name: str,
    row_number: int,
    cells: dict[int, str],
    groups: tuple[tuple[int, int | None, int], ...],
) -> list[VendorFact]:
    facts: list[VendorFact] = []
    for parameter_column, unit_column, offered_column in groups:
        label = cells.get(parameter_column, "").strip()
        raw_value = cells.get(offered_column, "").strip()
        if not label or not raw_value:
            continue
        if _normalize_header(label) in _TABLE_TERMINATORS or not _looks_like_label(label):
            continue
        if unit_column is not None:
            unit = cells.get(unit_column, "").strip()
            value, parsed_unit = _parse_numeric_value(raw_value)
            if value is not None and parsed_unit is None and unit:
                raw_value = f"{raw_value} {unit}"

        value, unit = _parse_numeric_value(raw_value)
        facts.append(
            VendorFact(
                parameter=label.lower(),
                raw_value=raw_value,
                value=value,
                unit=unit,
                source=SourceRef(document=path.name, line=row_number, section=sheet_name),
            )
        )
    return facts


def parse_xlsx_facts(path: str | Path) -> list[VendorFact]:
    """Parse explicit parameter/value tables from an XLSX vendor workbook."""
    file_path = Path(path)
    if file_path.suffix.lower() != ".xlsx":
        raise ValueError("XLSX vendor input must end in .xlsx")

    try:
        with zipfile.ZipFile(file_path) as archive:
            _validate_archive(archive)
            shared_strings = _shared_strings(archive)
            facts: list[VendorFact] = []
            for sheet_name, worksheet_path in _worksheet_paths(archive):
                active_groups: tuple[tuple[int, int | None, int], ...] = ()
                for row_number, cells in _sheet_rows(_read_member(archive, worksheet_path), shared_strings):
                    if not cells:
                        active_groups = ()
                        continue
                    groups = _header_groups(cells)
                    if groups:
                        active_groups = groups
                        continue
                    if not active_groups:
                        continue
                    if any(
                        _normalize_header(cells.get(parameter_column, "")) in _TABLE_TERMINATORS
                        for parameter_column, _, _ in active_groups
                    ):
                        active_groups = ()
                        continue
                    facts.extend(_row_facts(file_path, sheet_name, row_number, cells, active_groups))
            return facts
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid XLSX package") from exc
