from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(slots=True)
class PageText:
    page: int
    text: str


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
