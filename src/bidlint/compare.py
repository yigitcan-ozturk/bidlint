from __future__ import annotations

import math
from collections.abc import Mapping
from difflib import SequenceMatcher

from .models import ComplianceReport, Finding, Requirement, Status, VendorFact
from .terminology import canonical_parameter
from .units import canonical_unit, convert_value
from .vendor_package import is_conflict_fact


def _similarity(a: str, b: str, aliases: Mapping[str, str] | None = None) -> float:
    ca = canonical_parameter(a, aliases)
    cb = canonical_parameter(b, aliases)
    if ca == cb:
        return 1.0
    a_tokens, b_tokens = set(ca.split()), set(cb.split())
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    seq = SequenceMatcher(None, ca, cb).ratio()
    return max(overlap, seq)


def _evaluate(req: Requirement, fact: VendorFact) -> tuple[Status, str]:
    if is_conflict_fact(fact):
        return Status.REVIEW, fact.raw_value
    if req.operator is None or req.value is None:
        return Status.REVIEW, "Matched a vendor parameter, but the requirement is qualitative or not deterministically comparable."
    if fact.value is None:
        return Status.REVIEW, "Matched a vendor parameter, but the offered value is not numeric."

    actual = convert_value(fact.value, fact.unit, req.unit)
    if actual is None:
        return Status.REVIEW, f"Units require review: required {req.unit or 'unspecified'}, offered {fact.unit or 'unspecified'}."

    expected = req.value
    passed = {
        ">=": actual >= expected,
        "<=": actual <= expected,
        "=": math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12),
    }.get(req.operator)
    if passed is None:
        return Status.REVIEW, f"Unsupported comparison operator {req.operator}."

    offered_unit = canonical_unit(fact.unit) or ""
    required_unit = canonical_unit(req.unit) or ""
    offered_display = f"{fact.value:g}{offered_unit}"
    converted = fact.unit is not None and req.unit is not None and offered_unit != required_unit
    if converted:
        offered_display += f" (= {actual:g}{required_unit})"

    result = "satisfies" if passed else "does not satisfy"
    reason = f"Offered {offered_display} {result} {req.operator} {expected:g}{required_unit}."
    return (Status.PASS if passed else Status.DEVIATION), reason


def compare(
    requirements: list[Requirement],
    facts: list[VendorFact],
    specification: str,
    vendor: str,
    threshold: float = 0.52,
    aliases: Mapping[str, str] | None = None,
) -> ComplianceReport:
    findings: list[Finding] = []
    for req in requirements:
        ranked = sorted(
            ((_similarity(req.parameter, fact.parameter, aliases), fact) for fact in facts),
            key=lambda item: item[0],
            reverse=True,
        )
        if not ranked or ranked[0][0] < threshold:
            findings.append(
                Finding(
                    requirement=req,
                    vendor_fact=None,
                    status=Status.MISSING,
                    confidence=round(ranked[0][0], 3) if ranked else 0.0,
                    reason="No sufficiently similar vendor parameter was found.",
                )
            )
            continue
        score, fact = ranked[0]
        status, reason = _evaluate(req, fact)
        findings.append(
            Finding(
                requirement=req,
                vendor_fact=fact,
                status=status,
                confidence=round(score, 3),
                reason=reason,
            )
        )
    return ComplianceReport(specification=specification, vendor=vendor, findings=findings)
