from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .ifc import parse_ifc_facts
from .models import SourceRef, VendorFact
from .parse import parse_vendor_facts
from .terminology import canonical_parameter
from .units import canonical_unit, convert_value
from .xlsx_input import parse_xlsx_vendor_facts

_SUPPORTED_SUFFIXES = {".pdf", ".ifc", ".xlsx"}
_CONFLICT_SECTION = "bidlint:evidence-conflict"


@dataclass(slots=True)
class VendorPackage:
    root: Path
    documents: tuple[Path, ...]
    ignored_documents: tuple[Path, ...]
    facts: list[VendorFact]
    conflicts: list[VendorFact]


def _fact_location(fact: VendorFact) -> str:
    if fact.source is None:
        return "unknown source"
    location = fact.source.document
    if fact.source.page is not None:
        location += f":page {fact.source.page}"
    if fact.source.line is not None:
        location += f":line {fact.source.line}"
    if fact.source.section:
        location += f":{fact.source.section}"
    return location


def _facts_equivalent(left: VendorFact, right: VendorFact) -> bool:
    if left.value is not None and right.value is not None:
        if left.unit is None and right.unit is None:
            return math.isclose(left.value, right.value, rel_tol=1e-9, abs_tol=1e-12)
        if left.unit is None or right.unit is None:
            return False
        converted = convert_value(right.value, right.unit, left.unit)
        return converted is not None and math.isclose(left.value, converted, rel_tol=1e-9, abs_tol=1e-12)

    if (left.value is None) != (right.value is None):
        return False

    return (
        " ".join(left.raw_value.casefold().split()) == " ".join(right.raw_value.casefold().split())
        and canonical_unit(left.unit) == canonical_unit(right.unit)
    )


def _conflict_fact(root: Path, parameter: str, facts: list[VendorFact]) -> VendorFact:
    evidence = "; ".join(f"{_fact_location(fact)} = {fact.raw_value}" for fact in facts)
    reason = f"Conflicting vendor evidence for {parameter}: {evidence}. Review required."
    return VendorFact(
        parameter=parameter,
        raw_value=reason,
        source=SourceRef(document=root.name, section=_CONFLICT_SECTION),
    )


def consolidate_package_facts(
    root: str | Path,
    facts: list[VendorFact],
    *,
    aliases: Mapping[str, str] | None = None,
) -> tuple[list[VendorFact], list[VendorFact]]:
    """Collapse duplicate package evidence and replace conflicts with explicit REVIEW facts."""
    root_path = Path(root)
    grouped: dict[str, list[VendorFact]] = {}
    for fact in facts:
        key = canonical_parameter(fact.parameter, aliases)
        grouped.setdefault(key, []).append(fact)

    consolidated: list[VendorFact] = []
    conflicts: list[VendorFact] = []
    for parameter, candidates in grouped.items():
        anchor = candidates[0]
        if all(_facts_equivalent(anchor, candidate) for candidate in candidates[1:]):
            consolidated.append(anchor)
            continue
        conflict = _conflict_fact(root_path, parameter, candidates)
        consolidated.append(conflict)
        conflicts.append(conflict)
    return consolidated, conflicts


def parse_vendor_package(
    path: str | Path,
    *,
    ifc_class: str | None = None,
    ifc_guid: str | None = None,
    ifc_pset: str | None = None,
    xlsx_sheet: str | None = None,
    aliases: Mapping[str, str] | None = None,
) -> VendorPackage:
    """Parse supported direct-child vendor documents as one deterministic evidence package."""
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"vendor package is not a directory: {root}")

    children = sorted(
        (child for child in root.iterdir() if child.is_file()),
        key=lambda child: (child.name.casefold(), child.name),
    )
    documents = tuple(child for child in children if child.suffix.lower() in _SUPPORTED_SUFFIXES)
    ignored = tuple(child for child in children if child.suffix.lower() not in _SUPPORTED_SUFFIXES)
    if not documents:
        raise ValueError("vendor package contains no supported .pdf, .ifc or .xlsx files")

    has_ifc = any(document.suffix.lower() == ".ifc" for document in documents)
    has_xlsx = any(document.suffix.lower() == ".xlsx" for document in documents)
    if any(value is not None for value in (ifc_class, ifc_guid, ifc_pset)) and not has_ifc:
        raise ValueError("IFC selection options require at least one .ifc file in the vendor package")
    if xlsx_sheet is not None and not has_xlsx:
        raise ValueError("--xlsx-sheet requires at least one .xlsx file in the vendor package")

    facts: list[VendorFact] = []
    for document in documents:
        suffix = document.suffix.lower()
        if suffix == ".pdf":
            facts.extend(parse_vendor_facts(document))
        elif suffix == ".ifc":
            facts.extend(
                parse_ifc_facts(
                    document,
                    ifc_class=ifc_class,
                    global_id=ifc_guid,
                    pset=ifc_pset,
                )
            )
        else:
            facts.extend(parse_xlsx_vendor_facts(document, sheet=xlsx_sheet))

    consolidated, conflicts = consolidate_package_facts(root, facts, aliases=aliases)
    return VendorPackage(
        root=root,
        documents=documents,
        ignored_documents=ignored,
        facts=consolidated,
        conflicts=conflicts,
    )


def is_conflict_fact(fact: VendorFact) -> bool:
    return fact.source is not None and fact.source.section == _CONFLICT_SECTION
