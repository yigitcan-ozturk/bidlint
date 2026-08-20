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


@dataclass(frozen=True, slots=True)
class PositionedRectangle:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(slots=True)
class PositionedRow:
    text: str
    fragments: tuple[PositionedText, ...]


@dataclass(slots=True)
class PositionedPage:
    page: int
    rows: tuple[PositionedRow, ...]
    rectangles: tuple[PositionedRectangle, ...] = ()


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


def _rectangle_user_bounds(args: list[Any], cm: list[float]) -> PositionedRectangle | None:
    """Transform an axis-aligned PDF ``re`` rectangle into page user space."""
    if len(args) < 4:
        return None
    # Rotated/skewed rectangle geometry is deliberately unsupported. Taking an
    # axis-aligned bounding box would make column membership look more certain
    # than the source geometry actually is.
    if abs(float(cm[1])) > 1e-6 or abs(float(cm[2])) > 1e-6:
        return None

    x, y, width, height = (float(args[i].as_numeric()) for i in range(4))
    x0 = x * float(cm[0]) + float(cm[4])
    x1 = (x + width) * float(cm[0]) + float(cm[4])
    y0 = y * float(cm[3]) + float(cm[5])
    y1 = (y + height) * float(cm[3]) + float(cm[5])
    left, right = sorted((x0, x1))
    bottom, top = sorted((y0, y1))
    if right - left < 1.0 or top - bottom < 1.0:
        return None
    return PositionedRectangle(x0=left, y0=bottom, x1=right, y1=top)


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
    """Extract conservative positioned text and explicit rectangle geometry.

    This supplementary pass does not replace layout-mode extraction. Multi-line
    text fragments are ignored because one coordinate cannot safely describe
    multiple visual rows. Rectangle geometry is collected only from explicit
    axis-aligned PDF ``re`` operators; arbitrary line drawings are not promoted
    to table cells.
    """
    file_path = Path(path)
    reader = PdfReader(str(file_path))
    pages: list[PositionedPage] = []

    for index, page in enumerate(reader.pages, start=1):
        fragments: list[PositionedText] = []
        rectangles: list[PositionedRectangle] = []

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

        def visitor_operand(operator: bytes, args: list[Any], cm: list[float], _tm: list[float]) -> None:
            if operator != b"re":
                return
            rectangle = _rectangle_user_bounds(args, cm)
            if rectangle is not None:
                rectangles.append(rectangle)

        page.extract_text(visitor_operand_before=visitor_operand, visitor_text=visitor_text)
        pages.append(
            PositionedPage(
                page=index,
                rows=_rows_from_fragments(fragments, y_tolerance=y_tolerance),
                rectangles=tuple(rectangles),
            )
        )

    return pages
