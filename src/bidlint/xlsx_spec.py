from __future__ import annotations

import re
import zipfile
from pathlib import Path

from .models import Requirement, SourceRef
from .xlsx_input import _rows, _select_sheet, _shared_strings, _validate_archive, _workbook_sheets

_SPEC_PARAMETER_HEADERS = {
    "general requirement",
    "requirement",
    "parameter",
    "property",
    "technical requirement",
}
_SPEC_VALUE_HEADERS = {
    "specification",
    "required value",
    "requirement value",
    "value",
}
_NUMERIC_VALUE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/^\-²³]+)?\s*$")
_COMPARATOR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?:minimum|at least|not less than|no less than|>=)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?",
            re.IGNORECASE,
        ),
        ">=",
    ),
    (
        re.compile(
            r"(?:maximum|not more than|no more than|not exceed|<=)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?",
            re.IGNORECASE,
        ),
        "<=",
    ),
]


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


def _spec_header(rows: list[tuple[int, dict[int, str]]]) -> tuple[int, int, int]:
    for row_number, values in rows[:20]:
        normalized = {column: _normalize_header(value) for column, value in values.items()}
        parameter_cols = [column for column, value in normalized.items() if value in _SPEC_PARAMETER_HEADERS]
        value_cols = [column for column, value in normalized.items() if value in _SPEC_VALUE_HEADERS]
        if not parameter_cols or not value_cols:
            continue
        if len(parameter_cols) != 1 or len(value_cols) != 1:
            raise ValueError(
                "XLSX specification header must contain exactly one requirement column and one specification column"
            )
        return row_number, parameter_cols[0], value_cols[0]
    raise ValueError(
        "XLSX specification requires an explicit requirement/specification header row within the first 20 populated rows"
    )


def _comparison(raw: str) -> tuple[str | None, float | None, str | None]:
    for pattern, operator in _COMPARATOR_PATTERNS:
        match = pattern.search(raw)
        if match:
            return operator, float(match.group(1)), _normalize_unit(match.group(2))

    numeric = _NUMERIC_VALUE.fullmatch(raw)
    if numeric:
        return "=", float(numeric.group(1)), _normalize_unit(numeric.group(2))
    return None, None, None


def parse_xlsx_requirements(path: str | Path, *, sheet: str | None = None) -> list[Requirement]:
    """Parse a conservative key/value requirement block from one visible XLSX worksheet.

    The parser intentionally consumes only the contiguous block immediately below
    an explicit Requirement/Specification-style header. A blank-row boundary ends
    that block, so a later item schedule is not silently flattened into unrelated
    requirements without an item-scoping model.
    """
    file_path = Path(path)
    if file_path.suffix.lower() != ".xlsx":
        raise ValueError("XLSX specification input must end in .xlsx")

    try:
        archive = zipfile.ZipFile(file_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("invalid XLSX specification input") from exc

    with archive:
        _validate_archive(archive)
        required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
        if required.difference(archive.namelist()):
            raise ValueError("invalid XLSX workbook package")
        shared = _shared_strings(archive)
        selected = _select_sheet(_workbook_sheets(archive), sheet)
        if selected.path not in archive.namelist():
            raise ValueError(f"worksheet package part missing for {selected.name}")
        root = __import__("xml.etree.ElementTree", fromlist=["ElementTree"]).fromstring(archive.read(selected.path))
        rows = _rows(root, shared)

    header_row, parameter_column, value_column = _spec_header(rows)
    candidates = [(row_number, values) for row_number, values in rows if row_number > header_row]
    requirements: list[Requirement] = []
    expected_row = header_row + 1

    for row_number, values in candidates:
        if row_number != expected_row:
            break
        expected_row += 1

        parameter = values.get(parameter_column, "").strip()
        required_value = values.get(value_column, "").strip()
        if not parameter and not required_value:
            continue
        if not parameter:
            raise ValueError(f"XLSX specification row {row_number} has a value but no requirement name")
        if not required_value:
            raise ValueError(f"XLSX specification row {row_number} has a requirement name but no value")

        operator, value, unit = _comparison(required_value)
        requirements.append(
            Requirement(
                id=f"R{len(requirements) + 1:04d}",
                text=f"{parameter}: {required_value}",
                parameter=parameter.lower(),
                operator=operator,
                value=value,
                unit=unit,
                mandatory=True,
                source=SourceRef(
                    document=file_path.name,
                    line=row_number,
                    section=f"XLSX:{selected.name}",
                ),
            )
        )

    if not requirements:
        raise ValueError("XLSX specification contains no populated requirements in the contiguous requirement block")
    return requirements
