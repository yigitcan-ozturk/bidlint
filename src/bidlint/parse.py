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
    (re.compile(r"(?:minimum|at least|not less than|no less than|>=)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?", re.I), ">="),
    (re.compile(r"(?:maximum|not more than|no more than|not exceed|<=)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?", re.I), "<="),
    (re.compile(r"(?:shall be|must be|required)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?", re.I), "="),
]

_KEY_VALUE = re.compile(r"^\s*([^:]{2,80}?)\s*:\s*(.+?)\s*$")
_NUMERIC = re.compile(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/\-²³]+)?")
_SECTION = re.compile(r"^\s*((?:\d+\.)+\d+|\d+(?:\.\d+){1,4})\s+(.+)$")

_STOPWORDS = {
    "the", "a", "an", "shall", "must", "be", "is", "are", "required", "minimum", "maximum",
    "at", "least", "not", "less", "than", "more", "no", "of", "to", "for", "and", "with",
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
                    mandatory=bool(re.search(r"\b(shall|must|required)\b", line, re.I)),
                    source=SourceRef(document=path.name, page=page.page, line=line_no, section=current_section),
                )
            )
            counter += 1
    return requirements


def parse_vendor_facts(path: str | Path) -> list[VendorFact]:
    path = Path(path)
    pages = extract_pages(path)
    facts: list[VendorFact] = []

    for page in pages:
        lines = _split_lines(page)
        for line_no, line in lines:
            match = _KEY_VALUE.match(line)
            if not match:
                continue
            parameter = match.group(1).strip().lower()
            raw_value = match.group(2).strip()
            num = _NUMERIC.search(raw_value)
            value = float(num.group(1)) if num else None
            unit = _normalize_unit(num.group(2)) if num else None
            facts.append(
                VendorFact(
                    parameter=parameter,
                    raw_value=raw_value,
                    value=value,
                    unit=unit,
                    source=SourceRef(document=path.name, page=page.page, line=line_no),
                )
            )
    return facts
