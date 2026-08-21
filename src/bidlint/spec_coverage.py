from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .xlsx_input import _select_sheet, _shared_strings, _validate_archive, _workbook_sheets
from .xlsx_spec import _spec_header, _spec_rows


def _xlsx_coverage(path: Path, *, sheet: str | None = None) -> dict[str, object]:
    try:
        archive = zipfile.ZipFile(path)
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
        root = ET.fromstring(archive.read(selected.path))
        rows = _spec_rows(root, shared)

    header_row, parameter_column, value_column = _spec_header(rows)
    candidates = [(row_number, values) for row_number, values in rows if row_number > header_row]
    evaluated_rows: list[int] = []
    first_unscoped_row: int | None = None
    expected_row = header_row + 1

    for row_number, values in candidates:
        if row_number != expected_row:
            first_unscoped_row = row_number
            break
        expected_row += 1
        parameter = values.get(parameter_column, "").strip()
        required_value = values.get(value_column, "").strip()
        if parameter and required_value:
            evaluated_rows.append(row_number)

    unscoped_rows = [
        row_number
        for row_number, _ in rows
        if first_unscoped_row is not None and row_number >= first_unscoped_row
    ]
    return {
        "kind": "xlsx",
        "coverage_observable": True,
        "header_row": header_row,
        "evaluated_requirement_row_count": len(evaluated_rows),
        "first_evaluated_row": evaluated_rows[0] if evaluated_rows else None,
        "last_evaluated_row": evaluated_rows[-1] if evaluated_rows else None,
        "unscoped_populated_row_count": len(unscoped_rows),
        "first_unscoped_row": unscoped_rows[0] if unscoped_rows else None,
        "last_populated_row": rows[-1][0] if rows else None,
        "manual_scope_review_required": bool(unscoped_rows),
    }


def specification_coverage(path: str | Path, *, xlsx_sheet: str | None = None) -> dict[str, object]:
    """Return non-content specification scope evidence for pilot review.

    The result intentionally reports row counts and row numbers only. It does not
    copy specification cell text into pilot evidence.
    """
    source = Path(path)
    if source.suffix.lower() == ".xlsx":
        return _xlsx_coverage(source, sheet=xlsx_sheet)
    return {
        "kind": source.suffix.lower().lstrip(".") or "unknown",
        "coverage_observable": False,
        "manual_scope_review_required": False,
    }
