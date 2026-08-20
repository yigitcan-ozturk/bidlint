from __future__ import annotations

import re
from pathlib import Path

from .models import Requirement, SourceRef, VendorFact
from .pdf import PageText, extract_pages

_REQUIREMENT_HINT = re.compile(
    r"\b(shall|must|required|minimum|maximum|at least|not less than|not more than|not exceed|no less than|no more than)\b",
    re.IGNORECASE,
)

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
    (
        re.compile(
            r"(?:shall be|must be|required)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?",
            re.IGNORECASE,
        ),
        "=",
    ),
]

_KEY_VALUE = re.compile(r"^\s*([^:]{2,80}?)\s*:\s*(.+?)\s*$")
_LABEL_ONLY = re.compile(r"^\s*([^:]{2,80}?)\s*:\s*$")
_TWO_COLUMN = re.compile(r"^\s*(.{2,80}?)(?:\t+| {2,})(\S.*?)\s*$")
_NUMERIC_VALUE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/^\-²³]+)?\s*$")
_SECTION = re.compile(r"^\s*((?:\d+\.)+\d+|\d+(?:\.\d+){1,4})\s+(.+)$")
_COLUMN_GAP = re.compile(r"\s{2,}")

_PARAMETER_HEADERS = {
    "parameter",
    "property",
    "description",
    "technical parameter",
    "item",
}
_UNIT_HEADERS = {"unit", "units"}
_OFFERED_HEADERS = {
    "offered",
    "offered value",
    "vendor value",
    "supplier value",
    "value",
}
_TABLE_TERMINATORS = {"note", "notes", "remark", "remarks", "general notes"}

_STOPWORDS = {
    "the",
    "a",
    "an",
    "shall",
    "must",
    "be",
    "is",
    "are",
    "required",
    "minimum",
    "maximum",
    "at",
    "least",
    "not",
    "less",
    "than",
    "more",
    "no",
    "of",
    "to",
    "for",
    "and",
    "with",
}

TableHeader = tuple[int, int | None, int, int]


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    unit = unit.strip().lower().replace("º", "°")
    aliases = {
        "percent": "%",
        "percentage": "%",
        "degc": "°c",
        "c": "°c",
        "degrees": "°",
    }
    return aliases.get(unit, unit)


def _parameter_from_text(text: str, match_start: int | None = None) -> str:
    head = text[:match_start] if match_start is not None else text
    head = re.sub(r"^[\s\-•\d\.\)\(]+", "", head)
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-_/]*", head.lower())
    words = [w for w in words if w not in _STOPWORDS]
    if not words:
        words = re.findall(r"[A-Za-z][A-Za-z0-9\-_/]*", text.lower())
    return " ".join(words[-8:]).strip() or text[:80].strip().lower()


def _split_lines(page: PageText) -> list[tuple[int, str]]:
    return [(i, line.strip()) for i, line in enumerate(page.text.splitlines(), start=1) if line.strip()]


def _parse_numeric_value(raw_value: str) -> tuple[float | None, str | None]:
    """Parse only values that are wholly numeric + optional unit.

    Full matching is deliberate: alloy grades and descriptive values such as
    ``316L stainless steel`` remain qualitative instead of becoming a false
    numeric value of 316.
    """
    match = _NUMERIC_VALUE.fullmatch(raw_value)
    if not match:
        return None, None
    return float(match.group(1)), _normalize_unit(match.group(2))


def _looks_like_label(text: str) -> bool:
    text = text.strip()
    if not 2 <= len(text) <= 80:
        return False
    if not re.search(r"[A-Za-z]", text):
        return False
    if _SECTION.match(text) or _REQUIREMENT_HINT.search(text):
        return False
    if _NUMERIC_VALUE.fullmatch(text):
        return False
    return True


def _parse_structured_vendor_line(line: str) -> tuple[str, str] | None:
    match = _KEY_VALUE.match(line)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    match = _TWO_COLUMN.match(line)
    if not match:
        return None
    label, raw_value = match.group(1).strip(), match.group(2).strip()
    if not _looks_like_label(label):
        return None
    return label, raw_value


def _make_vendor_fact(path: Path, page: PageText, line_no: int, label: str, raw_value: str) -> VendorFact:
    value, unit = _parse_numeric_value(raw_value)
    return VendorFact(
        parameter=label.strip().lower(),
        raw_value=raw_value.strip(),
        value=value,
        unit=unit,
        source=SourceRef(document=path.name, page=page.page, line=line_no),
    )


def _split_layout_columns(line: str) -> list[str]:
    return [cell.strip() for cell in _COLUMN_GAP.split(line.strip()) if cell.strip()]


def _normalize_header(cell: str) -> str:
    return " ".join(cell.lower().replace("_", " ").split())


def _table_header(columns: list[str]) -> TableHeader | None:
    normalized = [_normalize_header(cell) for cell in columns]
    parameter_index = next((i for i, cell in enumerate(normalized) if cell in _PARAMETER_HEADERS), None)
    offered_index = next((i for i, cell in enumerate(normalized) if cell in _OFFERED_HEADERS), None)
    if parameter_index is None or offered_index is None or parameter_index == offered_index:
        return None

    unit_index = next((i for i, cell in enumerate(normalized) if cell in _UNIT_HEADERS), None)
    return parameter_index, unit_index, offered_index, len(columns)


def _table_row_fact(
    path: Path,
    page: PageText,
    line_no: int,
    columns: list[str],
    header: TableHeader,
) -> VendorFact | None:
    parameter_index, unit_index, offered_index, header_width = header
    if len(columns) < header_width:
        return None

    label = columns[parameter_index].strip()
    if _normalize_header(label) in _TABLE_TERMINATORS or not _looks_like_label(label):
        return None

    raw_value = columns[offered_index].strip()
    if not raw_value:
        return None

    if unit_index is not None and unit_index < len(columns):
        unit = columns[unit_index].strip()
        value, parsed_unit = _parse_numeric_value(raw_value)
        if value is not None and parsed_unit is None and unit:
            raw_value = f"{raw_value} {unit}"

    return _make_vendor_fact(path, page, line_no, label, raw_value)


def _paired_layout_facts(
    path: Path,
    page: PageText,
    line_no: int,
    columns: list[str],
) -> list[VendorFact] | None:
    """Parse two numeric label/value pairs rendered on the same visual row."""
    if len(columns) != 4:
        return None

    label_a, value_a, label_b, value_b = columns
    if not (_looks_like_label(label_a) and _looks_like_label(label_b)):
        return None
    if not (_NUMERIC_VALUE.fullmatch(value_a) and _NUMERIC_VALUE.fullmatch(value_b)):
        return None

    return [
        _make_vendor_fact(path, page, line_no, label_a, value_a),
        _make_vendor_fact(path, page, line_no, label_b, value_b),
    ]


def parse_requirements(path: str | Path) -> list[Requirement]:
    path = Path(path)
    pages = extract_pages(path)
    requirements: list[Requirement] = []
    counter = 1
    current_section: str | None = None

    for page in pages:
        for line_no, line in _split_lines(page):
            section_match = _SECTION.match(line)
            if section_match and not _REQUIREMENT_HINT.search(line):
                current_section = section_match.group(1)
                continue
            if not _REQUIREMENT_HINT.search(line):
                continue

            operator = None
            value = None
            unit = None
            normative = _REQUIREMENT_HINT.search(line)
            parameter = _parameter_from_text(line, normative.start()) if normative else _parameter_from_text(line)
            for pattern, parsed_operator in _COMPARATOR_PATTERNS:
                match = pattern.search(line)
                if match:
                    operator = parsed_operator
                    value = float(match.group(1))
                    unit = _normalize_unit(match.group(2))
                    parameter = _parameter_from_text(line, match.start())
                    break

            requirements.append(
                Requirement(
                    id=f"R{counter:04d}",
                    text=line,
                    parameter=parameter,
                    operator=operator,
                    value=value,
                    unit=unit,
                    mandatory=bool(re.search(r"\b(shall|must|required)\b", line, re.IGNORECASE)),
                    source=SourceRef(document=path.name, page=page.page, line=line_no, section=current_section),
                )
            )
            counter += 1
    return requirements


def parse_vendor_facts(path: str | Path) -> list[VendorFact]:
    """Extract deterministic vendor facts from common datasheet layouts.

    Supported forms are deliberately explicit:

    - ``Parameter: value``
    - two-column rows separated by a tab or at least two spaces
    - ``Parameter:`` followed by a value on the next non-empty line
    - a label followed by a *numeric + unit* value on the next line
    - layout-preserved tables with explicit parameter/value headers
    - two numeric label/value pairs rendered side-by-side on one visual row

    Table reconstruction remains conservative: only explicit headers or fully
    numeric side-by-side pairs are accepted. Ambiguous 3+ column rows are
    skipped rather than flattened into false facts.
    """
    path = Path(path)
    pages = extract_pages(path, layout=True)
    facts: list[VendorFact] = []

    for page in pages:
        lines = _split_lines(page)
        index = 0
        active_table: TableHeader | None = None
        while index < len(lines):
            line_no, line = lines[index]
            columns = _split_layout_columns(line)

            header = _table_header(columns)
            if header is not None:
                active_table = header
                index += 1
                continue

            if active_table is not None:
                table_fact = _table_row_fact(path, page, line_no, columns, active_table)
                if table_fact is not None:
                    facts.append(table_fact)
                    index += 1
                    continue

                active_table = None
                if columns and _normalize_header(columns[0]) in _TABLE_TERMINATORS:
                    index += 1
                    continue

            paired = _paired_layout_facts(path, page, line_no, columns)
            if paired is not None:
                facts.extend(paired)
                index += 1
                continue

            # A visually separated 3+ column row without a recognized table
            # schema is ambiguous. Do not flatten it into a fake two-column fact.
            if len(columns) >= 3:
                index += 1
                continue

            structured = _parse_structured_vendor_line(line)
            if structured:
                label, raw_value = structured
                facts.append(_make_vendor_fact(path, page, line_no, label, raw_value))
                index += 1
                continue

            label_only = _LABEL_ONLY.match(line)
            if label_only and index + 1 < len(lines):
                _, next_line = lines[index + 1]
                if len(next_line) <= 120 and not _SECTION.match(next_line) and not _KEY_VALUE.match(next_line):
                    facts.append(
                        _make_vendor_fact(
                            path,
                            page,
                            line_no,
                            label_only.group(1),
                            next_line,
                        )
                    )
                    index += 2
                    continue

            if _looks_like_label(line) and index + 1 < len(lines):
                _, next_line = lines[index + 1]
                if _NUMERIC_VALUE.fullmatch(next_line):
                    facts.append(_make_vendor_fact(path, page, line_no, line, next_line))
                    index += 2
                    continue

            index += 1

    return facts
