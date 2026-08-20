from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .models import (
    ComplianceReport,
    KnockoutAssessment,
    KnockoutCriterion,
    KnockoutStatus,
    Requirement,
    Status,
)

_ALLOWED_KEYS = {"requirement_ids"}


def normalize_knockout_requirement_ids(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("knockout requirement_ids must be a sequence of IDs, not a string")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("knockout requirement_ids must contain non-empty strings")
        requirement_id = value.strip()
        if requirement_id in seen:
            raise ValueError(f"duplicate knockout requirement id: {requirement_id}")
        seen.add(requirement_id)
        normalized.append(requirement_id)
    if not normalized:
        raise ValueError("knockout requirement_ids must not be empty")
    return tuple(normalized)


def load_knockout_file(path: str | Path) -> tuple[str, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("knockout policy must be a JSON object")

    unknown = sorted(set(data) - _ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"unknown knockout policy key(s): {', '.join(unknown)}")
    if "requirement_ids" not in data:
        raise ValueError("knockout policy requires requirement_ids")
    requirement_ids = data["requirement_ids"]
    if not isinstance(requirement_ids, list):
        raise ValueError("knockout requirement_ids must be a JSON array")
    return normalize_knockout_requirement_ids(requirement_ids)


def validate_knockout_requirement_ids(
    requirements: Sequence[Requirement],
    requirement_ids: Sequence[str],
) -> tuple[str, ...]:
    normalized = normalize_knockout_requirement_ids(requirement_ids)
    known = {requirement.id for requirement in requirements}
    unknown = [requirement_id for requirement_id in normalized if requirement_id not in known]
    if unknown:
        raise ValueError(f"unknown knockout requirement id(s): {', '.join(unknown)}")
    return normalized


def apply_knockouts(
    report: ComplianceReport,
    requirement_ids: Sequence[str],
) -> KnockoutAssessment:
    normalized = normalize_knockout_requirement_ids(requirement_ids)

    findings_by_id = {}
    duplicate_finding_ids: set[str] = set()
    for finding in report.findings:
        requirement_id = finding.requirement.id
        if requirement_id in findings_by_id:
            duplicate_finding_ids.add(requirement_id)
        findings_by_id[requirement_id] = finding

    ambiguous = sorted(set(normalized) & duplicate_finding_ids)
    if ambiguous:
        raise ValueError(f"duplicate report finding id(s) cannot be knockout criteria: {', '.join(ambiguous)}")

    unknown = [requirement_id for requirement_id in normalized if requirement_id not in findings_by_id]
    if unknown:
        raise ValueError(f"unknown knockout requirement id(s): {', '.join(unknown)}")

    criteria: list[KnockoutCriterion] = []
    has_failure = False
    has_review = False
    for requirement_id in normalized:
        finding = findings_by_id[requirement_id]
        criteria.append(
            KnockoutCriterion(
                requirement_id=requirement_id,
                parameter=finding.requirement.parameter,
                finding_status=finding.status,
                reason=finding.reason,
            )
        )
        if finding.status in {Status.DEVIATION, Status.MISSING}:
            has_failure = True
        elif finding.status == Status.REVIEW:
            has_review = True

    if has_failure:
        status = KnockoutStatus.DISQUALIFIED
    elif has_review:
        status = KnockoutStatus.REVIEW_REQUIRED
    else:
        status = KnockoutStatus.ELIGIBLE

    assessment = KnockoutAssessment(status=status, criteria=criteria)
    report.knockout = assessment
    return assessment
