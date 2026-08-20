from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path


class DocumentClass(str, Enum):
    SPECIFICATION = "specification"
    DATASHEET = "datasheet"
    COMPLIANCE_SCHEDULE = "compliance-schedule"
    TECHNICAL_OFFER = "technical-offer"
    IGNORED = "ignored"


_EVIDENCE_CLASSES = {
    DocumentClass.DATASHEET,
    DocumentClass.COMPLIANCE_SCHEDULE,
    DocumentClass.TECHNICAL_OFFER,
}
_SUPPORTED_SUFFIXES = {".pdf", ".ifc", ".xlsx"}
_IGNORED_MARKERS = {"commercial", "price", "pricing", "quotation", "quote"}
_DATASHEET_MARKERS = {"datasheet", "data sheet", "catalog", "catalogue"}
_SPECIFICATION_MARKERS = {"spec", "specification", "requirement", "requirements"}
_TECHNICAL_OFFER_MARKERS = {"offer", "proposal", "submittal", "submission", "technical offer"}


def parse_document_class(value: str | DocumentClass) -> DocumentClass:
    if isinstance(value, DocumentClass):
        return value
    normalized = value.strip().casefold().replace("_", "-").replace(" ", "-")
    try:
        return DocumentClass(normalized)
    except ValueError as exc:
        choices = ", ".join(item.value for item in DocumentClass)
        raise ValueError(f"unknown document class {value!r}; expected one of: {choices}") from exc


def is_evidence_class(document_class: DocumentClass | str) -> bool:
    return parse_document_class(document_class) in _EVIDENCE_CLASSES


def _normalized_name(path: Path) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", path.stem.casefold())
    return " ".join(words.split())


def _contains_marker(name: str, markers: Iterable[str]) -> bool:
    padded = f" {name} "
    return any(f" {marker} " in padded for marker in markers)


def classify_document(path: str | Path) -> DocumentClass:
    """Classify one package document using deterministic, auditable filename rules."""
    document = Path(path)
    if document.suffix.lower() not in _SUPPORTED_SUFFIXES:
        return DocumentClass.IGNORED

    name = _normalized_name(document)
    if _contains_marker(name, _IGNORED_MARKERS):
        return DocumentClass.IGNORED
    if "compliance" in name:
        return DocumentClass.COMPLIANCE_SCHEDULE
    if _contains_marker(name, _DATASHEET_MARKERS):
        return DocumentClass.DATASHEET
    if _contains_marker(name, _SPECIFICATION_MARKERS):
        return DocumentClass.SPECIFICATION
    if _contains_marker(name, _TECHNICAL_OFFER_MARKERS):
        return DocumentClass.TECHNICAL_OFFER

    # Conservative format fallbacks keep existing v0.7 package behaviour stable while
    # making the classification visible and overridable instead of hiding precedence.
    if document.suffix.lower() == ".xlsx":
        return DocumentClass.COMPLIANCE_SCHEDULE
    return DocumentClass.TECHNICAL_OFFER


def classify_documents(
    documents: Sequence[Path],
    overrides: Mapping[str, DocumentClass | str] | None = None,
) -> dict[str, DocumentClass]:
    by_name = {document.name: document for document in documents}
    overrides = overrides or {}
    unknown = sorted(set(overrides) - set(by_name))
    if unknown:
        raise ValueError(f"document-class override does not match a package file: {', '.join(unknown)}")

    classifications: dict[str, DocumentClass] = {}
    for document in documents:
        if document.name in overrides:
            document_class = parse_document_class(overrides[document.name])
        else:
            document_class = classify_document(document)
        if document.suffix.lower() not in _SUPPORTED_SUFFIXES and document_class is not DocumentClass.IGNORED:
            raise ValueError(f"unsupported document {document.name} can only be classified as ignored")
        classifications[document.name] = document_class
    return classifications


def normalize_evidence_priority(
    priority: Sequence[DocumentClass | str] | None,
) -> tuple[DocumentClass, ...]:
    if not priority:
        return ()
    normalized = tuple(parse_document_class(item) for item in priority)
    invalid = [item.value for item in normalized if item not in _EVIDENCE_CLASSES]
    if invalid:
        raise ValueError(
            "evidence priority can only contain datasheet, compliance-schedule and technical-offer"
        )
    if len(set(normalized)) != len(normalized):
        raise ValueError("evidence priority cannot contain duplicate document classes")
    return normalized
