from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import ComplianceReport, Finding, Requirement, Status, VendorFact

_UNIT_EQUIVALENTS = {
    ("°c", "c"),
    ("c", "°c"),
}

_SYNONYMS = {
    "ingress protection": "ip rating",
    "protection class": "ip rating",
    "sound pressure": "noise level",
    "operating temp": "operating temperature",
}


def _canon(text: str) -> str:
    text = text.lower().strip()
    text = _SYNONYMS.get(text, text)
    text = re.sub(r"[^a-z0-9%°]+", " ", text)
    return " ".join(text.split())


def _similarity(a: str, b: str) -> float:
    ca, cb = _canon(a), _canon(b)
    if ca == cb:
        return 1.0
    a_tokens, b_tokens = set(ca.split()), set(cb.split())
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    seq = SequenceMatcher(None, ca, cb).ratio()
    return max(overlap, seq)


def _compatible_units(req: str | None, offered: str | None) -> bool:
    if req is None or offered is None:
        return True
    return req == offered or (req, offered) in _UNIT_EQUIVALENTS


def _evaluate(req: Requirement, fact: VendorFact) -> tuple[Status, str]:
    if req.operator is None or req.value is None:
        return Status.REVIEW, "Matched a vendor parameter, but the requirement is qualitative or not deterministically comparable."
    if fact.value is None:
        return Status.REVIEW, "Matched a vendor parameter, but the offered value is not numeric."
    if not _compatible_units(req.unit, fact.unit):
        return Status.REVIEW, f"Units require review: required {req.unit or 'unspecified'}, offered {fact.unit or 'unspecified'}."

    actual = fact.value
    expected = req.value
    passed = {
        ">=": actual >= expected,
        "<=": actual <= expected,
        "=": actual == expected,
    }.get(req.operator)
    if passed is None:
        return Status.REVIEW, f"Unsupported comparison operator {req.operator}."
    if passed:
        return Status.PASS, f"Offered {actual:g}{fact.unit or ''} satisfies {req.operator} {expected:g}{req.unit or ''}."
    return Status.DEVIATION, f"Offered {actual:g}{fact.unit or ''} does not satisfy {req.operator} {expected:g}{req.unit or ''}."


def compare(requirements: list[Requirement], facts: list[VendorFact], specification: str, vendor: str, threshold: float = 0.52) -> ComplianceReport:
    findings: list[Finding] = []
    for req in requirements:
        ranked = sorted(((_similarity(req.parameter, fact.parameter), fact) for fact in facts), key=lambda item: item[0], reverse=True)
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
        findings.append(Finding(requirement=req, vendor_fact=fact, status=status, confidence=round(score, 3), reason=reason))
    return ComplianceReport(specification=specification, vendor=vendor, findings=findings)
