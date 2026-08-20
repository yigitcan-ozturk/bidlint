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


def _finite_number(value: object) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))


def _validate_common(
    candidate: ExtractionCandidate,
    pages: dict[int, PageText],
    *,
    min_confidence: float,
) -> str | None:
    confidence = candidate.confidence
    if not _finite_number(confidence) or confidence is None or not 0.0 <= confidence <= 1.0:
        return "confidence must be a finite number between 0 and 1"
    if confidence < min_confidence:
        return f"confidence {confidence:.3f} is below minimum {min_confidence:.3f}"

    evidence = candidate.evidence
    if not isinstance(evidence, Evidence):
        return "evidence object is required"
    if not isinstance(evidence.page, int) or isinstance(evidence.page, bool) or evidence.page < 1:
        return "evidence page must be a positive integer"
    if evidence.page not in pages:
        return f"evidence page {evidence.page} is outside the source document"
    if evidence.line is not None and (
        not isinstance(evidence.line, int) or isinstance(evidence.line, bool) or evidence.line < 1
    ):
        return "evidence line must be a positive integer when supplied"
    if not isinstance(evidence.text, str) or not evidence.text.strip():
        return "evidence text is required"

    normalized_evidence = _normalize_evidence(evidence.text)
    page_text = _normalize_evidence(pages[evidence.page].text)
    if normalized_evidence not in page_text:
        return "evidence text was not found on the declared source page"
    return None


def _validate_requirement(candidate: RequirementCandidate) -> str | None:
    if not isinstance(candidate.text, str) or not candidate.text.strip():
        return "requirement text is required"
    if not isinstance(candidate.parameter, str) or not candidate.parameter.strip():
        return "requirement parameter is required"
    if candidate.operator is not None and candidate.operator not in _ALLOWED_OPERATORS:
        return f"unsupported requirement operator {candidate.operator!r}"
    if not _finite_number(candidate.value):
        return "requirement value must be finite when supplied"
    if (candidate.operator is None) != (candidate.value is None):
        return "requirement operator and numeric value must be supplied together"
    if candidate.unit is not None and not isinstance(candidate.unit, str):
        return "requirement unit must be text when supplied"
    if not isinstance(candidate.mandatory, bool):
        return "requirement mandatory flag must be boolean"
    return None


def _validate_vendor_fact(candidate: VendorFactCandidate) -> str | None:
    if not isinstance(candidate.parameter, str) or not candidate.parameter.strip():
        return "vendor parameter is required"
    if not isinstance(candidate.raw_value, str) or not candidate.raw_value.strip():
        return "vendor raw value is required"
    if not _finite_number(candidate.value):
        return "vendor numeric value must be finite when supplied"
    if candidate.unit is not None and not isinstance(candidate.unit, str):
        return "vendor unit must be text when supplied"
    return None


def _source_ref(document: Path, evidence: Evidence) -> SourceRef:
    return SourceRef(
        document=document.name,
        page=evidence.page,
        line=evidence.line,
        section=evidence.section if isinstance(evidence.section, str) else None,
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
    if not _finite_number(min_confidence) or min_confidence is None or not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be a finite number between 0 and 1")
    if not isinstance(batch.provider, str) or not batch.provider.strip():
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
        returned_kind = batch.kind.value if isinstance(batch.kind, ExtractionKind) else repr(batch.kind)
        raise ValueError(f"provider returned {returned_kind!r} for requested {kind.value!r} extraction")
    if not isinstance(extractor.name, str) or not extractor.name.strip():
        raise ValueError("extractor name is required")
    if not isinstance(batch.provider, str) or batch.provider.strip() != extractor.name.strip():
        raise ValueError("provider batch name does not match extractor name")
    return validate_extraction(document_path, batch, min_confidence=min_confidence)
