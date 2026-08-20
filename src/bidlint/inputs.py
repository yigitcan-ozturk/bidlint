from __future__ import annotations

from pathlib import Path

from .ifc import parse_ifc_facts
from .models import VendorFact
from .parse import parse_vendor_facts
from .xlsx_input import parse_xlsx_facts


def parse_vendor_input(
    path: str | Path,
    *,
    ifc_class: str | None = None,
    ifc_guid: str | None = None,
    ifc_pset: str | None = None,
) -> list[VendorFact]:
    """Parse a supported vendor input while keeping IFC selection explicit."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix in {".pdf", ".xlsx"}:
        if any(value is not None for value in (ifc_class, ifc_guid, ifc_pset)):
            raise ValueError("IFC selection options can only be used with .ifc vendor inputs")
        if suffix == ".pdf":
            return parse_vendor_facts(file_path)
        return parse_xlsx_facts(file_path)
    if suffix == ".ifc":
        return parse_ifc_facts(
            file_path,
            ifc_class=ifc_class,
            global_id=ifc_guid,
            pset=ifc_pset,
        )
    raise ValueError("vendor input must end in .pdf, .xlsx or .ifc")
