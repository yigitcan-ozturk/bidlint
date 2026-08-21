from __future__ import annotations

from pathlib import Path

from .models import Requirement
from .parse import parse_requirements
from .xlsx_spec import parse_xlsx_requirements


def parse_specification_input(path: str | Path, *, xlsx_sheet: str | None = None) -> list[Requirement]:
    """Parse a supported specification file without changing frozen comparison semantics."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        if xlsx_sheet is not None:
            raise ValueError("--spec-xlsx-sheet can only be used with .xlsx specification inputs")
        return parse_requirements(file_path)
    if suffix == ".xlsx":
        return parse_xlsx_requirements(file_path, sheet=xlsx_sheet)
    raise ValueError("specification input must end in .pdf or .xlsx")
