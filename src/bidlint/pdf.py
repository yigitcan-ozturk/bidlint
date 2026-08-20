from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


@dataclass(slots=True)
class PageText:
    page: int
    text: str


@dataclass(slots=True)
class PositionedText:
    text: str
    x: float
    y: float


@dataclass(slots=True)
class PositionedRow:
    text: str
    fragments: tuple[PositionedText, ...]


@dataclass(slots=True)
class PositionedPage:
    page: int
    rows: tuple[PositionedRow, ...]


def extract_pages(path: str | Path, *, layout: bool = False) -> list[PageText]:
    """Extract text page-by-page while preserving source page numbers.

    Layout mode keeps horizontal spacing for vendor datasheets so explicit
    table columns can be reconstructed conservatively. Requirement parsing
    continues to use ordinary text extraction.
    """
    file_path = Path(path)
    reader = PdfReader(str(file_path))
    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        if layout:
            text = (
                page.extract_text(
                    extraction_mode="layout",
                    layout_mode_space_vertically=False,
                )
                or ""
            )
        else:
            text = page.extract_text() or ""
        pages.append(PageText(page=index, text=text))
    return pages


def _single_line_fragment(text: str) -> str | None:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    return lines[0]


def _text_user_position(cm: list[float], tm: list[float]) -> tuple[float, float]:
    """Map a text-matrix origin into page user space without using pypdf internals."""
    x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
    y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
    return float(x), float(y)


def _rows_from_fragments(fragments: list[PositionedText], *, y_tolerance: float) -> tuple[PositionedRow, ...]:
    if not fragments:
        return ()

    fragments.sort(key=lambda fragment: (-fragment.y, fragment.x))
    rows: list[PositionedRow] = []
    current: list[PositionedText] = []
    baseline: float | None = None

    def flush() -> None:
        nonlocal current, baseline
        if not current:
            return
        ordered = tuple(sorted(current, key=lambda fragment: fragment.x))
        rows.append(PositionedRow(text=" ".join(fragment.text for fragment in ordered), fragments=ordered))
        current = []
        baseline = None

    for fragment in fragments:
        if baseline is None:
            baseline = fragment.y
            current.append(fragment)
            continue
        if abs(fragment.y - baseline) <= y_tolerance:
            current.append(fragment)
            continue
        flush()
        baseline = fragment.y
        current.append(fragment)

    flush()
    return tuple(rows)


def extract_positioned_pages(path: str | Path, *, y_tolerance: float = 2.0) -> list[PositionedPage]:
    """Extract single-line text fragments with conservative page coordinates.

    This is a supplementary pass for sparse table reconstruction. It does not
    replace layout-mode extraction and deliberately ignores text fragments that
    contain multiple non-empty lines because one coordinate cannot safely
    describe multiple visual rows.
    """
    file_path = Path(path)
    reader = PdfReader(str(file_path))
    pages: list[PositionedPage] = []

    for index, page in enumerate(reader.pages, start=1):
        fragments: list[PositionedText] = []

        def visitor_text(
            text: str,
            cm: list[float],
            tm: list[float],
            _font_dictionary: Any,
            _font_size: float,
        ) -> None:
            cleaned = _single_line_fragment(text)
            if not cleaned:
                return
            x, y = _text_user_position(cm, tm)
            fragments.append(PositionedText(text=cleaned, x=x, y=y))

        page.extract_text(visitor_text=visitor_text)
        pages.append(PositionedPage(page=index, rows=_rows_from_fragments(fragments, y_tolerance=y_tolerance)))

    return pages
