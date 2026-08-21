from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from . import __version__
from .models import ComplianceReport, Finding, Status

_CONTRACT = "bidlint.procurement-clarifications"
_PORTFOLIO_CONTRACT = "bidlint.procurement-clarifications-portfolio"
_CONTRACT_VERSION = "1"


def _source_dict(source) -> dict | None:
    if source is None:
        return None
    return {
        "document": source.document,
        "page": source.page,
        "line": source.line,
        "section": source.section,
    }


def _evidence_dict(finding: Finding) -> dict | None:
    fact = finding.vendor_fact
    if fact is None:
        return None
    return {
        "parameter": fact.parameter,
        "raw_value": fact.raw_value,
        "value": fact.value,
        "unit": fact.unit,
        "source": _source_dict(fact.source),
    }


def _validate_unique_requirement_ids(report: ComplianceReport) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for finding in report.findings:
        requirement_id = finding.requirement.id
        if requirement_id in seen:
            duplicates.add(requirement_id)
        seen.add(requirement_id)
    if duplicates:
        raise ValueError(
            "duplicate requirement id(s) in report: " + ", ".join(sorted(duplicates))
        )


def _question_for(finding: Finding) -> str:
    req = finding.requirement
    if finding.status == Status.REVIEW:
        return (
            f"Please clarify requirement {req.id} ({req.parameter}) and provide "
            "unambiguous technical evidence confirming the offered value or compliance."
        )
    if finding.status == Status.MISSING:
        return (
            f"Please provide technical evidence addressing requirement {req.id} "
            f"({req.parameter})."
        )
    raise ValueError("clarification records require REVIEW or MISSING findings")


def _record(finding: Finding, category: str) -> dict:
    req = finding.requirement
    return {
        "category": category,
        "status": "OPEN",
        "requirement_id": req.id,
        "parameter": req.parameter,
        "requirement_text": req.text,
        "question": _question_for(finding),
        "finding_status": finding.status.value,
        "confidence": finding.confidence,
        "evaluator_reason": finding.reason,
        "specification_source": _source_dict(req.source),
        "vendor_evidence": _evidence_dict(finding),
    }


def clarification_register(report: ComplianceReport) -> dict:
    _validate_unique_requirement_ids(report)
    clarifications = [
        _record(finding, "BIDDER_CLARIFICATION")
        for finding in report.findings
        if finding.status == Status.REVIEW
    ]
    unanswered = [
        _record(finding, "UNANSWERED_REQUIREMENT")
        for finding in report.findings
        if finding.status == Status.MISSING
    ]
    return {
        "contract": _CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": report.specification,
        "vendor": report.vendor,
        "counts": {
            "bidder_clarifications": len(clarifications),
            "unanswered_requirements": len(unanswered),
            "open_items": len(clarifications) + len(unanswered),
        },
        "bidder_clarifications": clarifications,
        "unanswered_requirements": unanswered,
    }


def clarification_portfolio(reports: Iterable[ComplianceReport]) -> dict:
    registers = [clarification_register(report) for report in reports]
    return {
        "contract": _PORTFOLIO_CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "vendor_count": len(registers),
        "open_items": sum(item["counts"]["open_items"] for item in registers),
        "registers": registers,
    }


def clarification_json(report: ComplianceReport) -> str:
    return json.dumps(clarification_register(report), indent=2, ensure_ascii=False) + "\n"


def clarification_portfolio_json(reports: Iterable[ComplianceReport]) -> str:
    return json.dumps(clarification_portfolio(reports), indent=2, ensure_ascii=False) + "\n"


def write_clarification_register(report: ComplianceReport, path: str | Path) -> None:
    Path(path).write_text(clarification_json(report), encoding="utf-8")


def write_clarification_portfolio(reports: Iterable[ComplianceReport], path: str | Path) -> None:
    Path(path).write_text(clarification_portfolio_json(reports), encoding="utf-8")
