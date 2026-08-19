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

    The paired-line fallback is conservative so ordinary headings and prose do
    not silently become vendor facts.
    """
    path = Path(path)
    pages = extract_pages(path)
    facts: list[VendorFact] = []

    for page in pages:
        lines = _split_lines(page)
        index = 0
        while index < len(lines):
            line_no, line = lines[index]

            structured = _parse_structured_vendor_line(line)
            if structured:
                label, raw_value = structured
                facts.append(_make_vendor_fact(path, page, line_no, label, raw_value))
                index += 1
                continue

            label_only = _LABEL_ONLY.match(line)
            if label_only and index + 1 < len(lines):
                next_line_no, next_line = lines[index + 1]
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
                next_line_no, next_line = lines[index + 1]
                if _NUMERIC_VALUE.fullmatch(next_line):
                    facts.append(_make_vendor_fact(path, page, line_no, line, next_line))
                    index += 2
                    continue

            index += 1

    return facts
