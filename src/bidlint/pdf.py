from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(slots=True)
class PageText:
    page: int
    text: str


def extract_pages(path: str | Path) -> list[PageText]:
    """Extract text page-by-page while preserving source page numbers."""
    file_path = Path(path)
    reader = PdfReader(str(file_path))
    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageText(page=index, text=text))
    return pages
