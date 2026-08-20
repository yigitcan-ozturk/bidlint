from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from .document_policy import DocumentClass
from .ifc import parse_ifc_facts
from .models import VendorFact
from .parse import parse_vendor_facts
from .vendor_package import parse_vendor_package
from .xlsx_input import parse_xlsx_vendor_facts


def parse_vendor_input(
    path: str | Path,
    *,
    ifc_class: str | None = None,
    ifc_guid: str | None = None,
    ifc_pset: str | None = None,
    xlsx_sheet: str | None = None,
    aliases: Mapping[str, str] | None = None,
    document_classes: Mapping[str, DocumentClass | str] | None = None,
    evidence_priority: Sequence[DocumentClass | str] | None = None,
) -> list[VendorFact]:
    """Parse a supported vendor file or deterministic multi-file vendor package."""
    file_path = Path(path)
    if file_path.is_dir():
        package_options: dict[str, object] = {
            "ifc_class": ifc_class,
            "ifc_guid": ifc_guid,
            "ifc_pset": ifc_pset,
            "xlsx_sheet": xlsx_sheet,
        }
        if aliases is not None:
            package_options["aliases"] = aliases
        if document_classes is not None:
            package_options["document_classes"] = document_classes
        if evidence_priority is not None:
            package_options["evidence_priority"] = evidence_priority
        return parse_vendor_package(file_path, **package_options).facts

    if document_classes:
        raise ValueError("document-class overrides can only be used with vendor package directories")
    if evidence_priority:
        raise ValueError("evidence priority can only be used with vendor package directories")

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        if any(value is not None for value in (ifc_class, ifc_guid, ifc_pset)):
            raise ValueError("IFC selection options can only be used with .ifc vendor inputs")
        if xlsx_sheet is not None:
            raise ValueError("--xlsx-sheet can only be used with .xlsx vendor inputs")
        return parse_vendor_facts(file_path)
    if suffix == ".ifc":
        if xlsx_sheet is not None:
            raise ValueError("--xlsx-sheet can only be used with .xlsx vendor inputs")
        return parse_ifc_facts(
            file_path,
            ifc_class=ifc_class,
            global_id=ifc_guid,
            pset=ifc_pset,
        )
    if suffix == ".xlsx":
        if any(value is not None for value in (ifc_class, ifc_guid, ifc_pset)):
            raise ValueError("IFC selection options can only be used with .ifc vendor inputs")
        return parse_xlsx_vendor_facts(file_path, sheet=xlsx_sheet)
    raise ValueError("vendor input must be a directory or end in .pdf, .ifc or .xlsx")
