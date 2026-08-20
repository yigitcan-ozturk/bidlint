from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, TypeAlias

from .models import Requirement, SourceRef, VendorFact
from .pdf import PageText, extract_pages


class ExtractionKind(str, Enum):
    SPECIFICATION = "specification"
    VENDOR = "vendor"


@dataclass(slots=True)
class Evidence:
    """Provider-supplied provenance that must be verifiable in the source PDF."""

    page: int
    text: str
    line: int | None = None
    section: str | None = None


@dataclass(slots=True)
class RequirementCandidate:
    text: str
    parameter: str
    confidence: float
    evidence: Evidence
    operator: str | None = None
    value: float | None = None
    unit: str | None = None
    mandatory: bool = True


@dataclass(slots=True)
class VendorFactCandidate:
    parameter: str
    raw_value: str
    confidence: float
    evidence: Evidence
    value: float | None = None
    unit: str | None = None


ExtractionCandidate: TypeAlias = RequirementCandidate | VendorFactCandidate


@dataclass(slots=True)
class ExtractionBatch:
    """Structured output returned by an optional extraction provider."""

    provider: str
    kind: ExtractionKind
    candidates: list[ExtractionCandidate] = field(default_factory=list)


class StructuredExtractor(Protocol):
    """Provider-neutral adapter implemented by optional AI/extraction integrations."""

    name: str

    def extract(self, document: Path, kind: ExtractionKind) -> ExtractionBatch:
        """Return structured candidates with confidence and source evidence."""
        ...


@dataclass(slots=True)
class RejectedCandidate:
    index: int
    reason: str


@dataclass(slots=True)
class ValidatedExtraction:
    provider: str
    kind: ExtractionKind
    items: list[Requirement] | list[VendorFact]
    rejected: list[RejectedCandidate] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return len(self.items)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


_ALLOWED_OPERATORS = {">=", "<=", "="}
_WHITESPACE = re.compile(r"\s+")


def _normalize_evidence(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _finite_number(value: float | None) -> bool:
    return value is None or (isinstance(value, (int, float)) and math.isfinite(value))


def _validate_common(
    candidate: ExtractionCandidate,
    pages: dict[int, PageText],
    *,
    min_confidence: float,
) -> str | None:
    if not math.isfinite(candidate.confidence) or not 0.0 <= candidate.confidence <= 1.0:
        return "confidence must be a finite number between 0 and 1"
    if candidate.confidence < min_confidence:
        return f"confidence {candidate.confidence:.3f} is below minimum {min_confidence:.3f}"
    if candidate.evidence.page not in pages:
        return f"evidence page {candidate.evidence.page} is outside the source document"
    if candidate.evidence.line is not None and candidate.evidence.line < 1:
        return "evidence line must be at least 1 when supplied"

    evidence = _normalize_evidence(candidate.evidence.text)
    if not evidence:
        return "evidence text is required"
    page_text = _normalize_evidence(pages[candidate.evidence.page].text)
    if evidence not in page_text:
        return "evidence text was not found on the declared source page"
    return None


def _validate_requirement(candidate: RequirementCandidate) -> str | None:
    if not candidate.text.strip():
        return "requirement text is required"
    if not candidate.parameter.strip():
        return "requirement parameter is required"
    if candidate.operator is not None and candidate.operator not in _ALLOWED_OPERATORS:
        return f"unsupported requirement operator {candidate.operator!r}"
    if not _finite_number(candidate.value):
        return "requirement value must be finite when supplied"
    if (candidate.operator is None) != (candidate.value is None):
        return "requirement operator and numeric value must be supplied together"
    return None


def _validate_vendor_fact(candidate: VendorFactCandidate) -> str | None:
    if not candidate.parameter.strip():
        return "vendor parameter is required"
    if not candidate.raw_value.strip():
        return "vendor raw value is required"
    if not _finite_number(candidate.value):
        return "vendor numeric value must be finite when supplied"
    return None


def _source_ref(document: Path, evidence: Evidence) -> SourceRef:
    return SourceRef(
        document=document.name,
        page=evidence.page,
        line=evidence.line,
        section=evidence.section,
    )


def _requirement_from_candidate(document: Path, index: int, candidate: RequirementCandidate) -> Requirement:
    return Requirement(
        id=f"R{index:04d}",
        text=candidate.text.strip(),
        parameter=candidate.parameter.strip().lower(),
        operator=candidate.operator,
        value=float(candidate.value) if candidate.value is not None else None,
        unit=candidate.unit.strip().lower() if candidate.unit else None,
        mandatory=candidate.mandatory,
        source=_source_ref(document, candidate.evidence),
    )


def _vendor_fact_from_candidate(document: Path, candidate: VendorFactCandidate) -> VendorFact:
    return VendorFact(
        parameter=candidate.parameter.strip().lower(),
        raw_value=candidate.raw_value.strip(),
        value=float(candidate.value) if candidate.value is not None else None,
        unit=candidate.unit.strip().lower() if candidate.unit else None,
        source=_source_ref(document, candidate.evidence),
    )


def validate_extraction(
    document: str | Path,
    batch: ExtractionBatch,
    *,
    min_confidence: float = 0.75,
) -> ValidatedExtraction:
    """Validate provider output before converting it into deterministic core models.

    The validator requires confidence in ``[0, 1]``, a valid page number and an
    evidence snippet that is actually present on the declared PDF page. Invalid
    candidates are reported and never enter the deterministic evaluation core.
    """
    if not 0.0 <= min_confidence <= 1.0 or not math.isfinite(min_confidence):
        raise ValueError("min_confidence must be a finite number between 0 and 1")
    if not batch.provider.strip():
        raise ValueError("extraction provider name is required")

    document_path = Path(document)
    pages = {page.page: page for page in extract_pages(document_path)}
    rejected: list[RejectedCandidate] = []

    if batch.kind == ExtractionKind.SPECIFICATION:
        accepted_requirements: list[Requirement] = []
        for candidate_index, candidate in enumerate(batch.candidates, start=1):
            if not isinstance(candidate, RequirementCandidate):
                rejected.append(RejectedCandidate(candidate_index, "candidate type does not match specification extraction"))
                continue
            reason = _validate_common(candidate, pages, min_confidence=min_confidence) or _validate_requirement(candidate)
            if reason is not None:
                rejected.append(RejectedCandidate(candidate_index, reason))
                continue
            accepted_requirements.append(
                _requirement_from_candidate(document_path, len(accepted_requirements) + 1, candidate)
            )
        return ValidatedExtraction(
            provider=batch.provider.strip(),
            kind=batch.kind,
            items=accepted_requirements,
            rejected=rejected,
        )

    if batch.kind == ExtractionKind.VENDOR:
        accepted_facts: list[VendorFact] = []
        for candidate_index, candidate in enumerate(batch.candidates, start=1):
            if not isinstance(candidate, VendorFactCandidate):
                rejected.append(RejectedCandidate(candidate_index, "candidate type does not match vendor extraction"))
                continue
            reason = _validate_common(candidate, pages, min_confidence=min_confidence) or _validate_vendor_fact(candidate)
            if reason is not None:
                rejected.append(RejectedCandidate(candidate_index, reason))
                continue
            accepted_facts.append(_vendor_fact_from_candidate(document_path, candidate))
        return ValidatedExtraction(
            provider=batch.provider.strip(),
            kind=batch.kind,
            items=accepted_facts,
            rejected=rejected,
        )

    raise ValueError(f"unsupported extraction kind {batch.kind!r}")


def extract_with_provider(
    document: str | Path,
    kind: ExtractionKind,
    extractor: StructuredExtractor,
    *,
    min_confidence: float = 0.75,
) -> ValidatedExtraction:
    """Run an optional provider and validate its output before core conversion."""
    document_path = Path(document)
    batch = extractor.extract(document_path, kind)
    if batch.kind != kind:
        raise ValueError(f"provider returned {batch.kind.value!r} for requested {kind.value!r} extraction")
    if batch.provider.strip() != extractor.name.strip():
        raise ValueError("provider batch name does not match extractor name")
    return validate_extraction(document_path, batch, min_confidence=min_confidence)
