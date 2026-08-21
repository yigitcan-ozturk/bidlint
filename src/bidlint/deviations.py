from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from . import __version__
from .models import ComplianceReport, Finding, Status

_CONTRACT = "bidlint.procurement-review-register"
_PORTFOLIO_CONTRACT = "bidlint.procurement-review-register-portfolio"
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


def _knockout_ids(report: ComplianceReport) -> set[str]:
    if report.knockout is None:
        return set()
    return set(report.knockout.requirement_ids)


def _record(report: ComplianceReport, finding: Finding, category: str) -> dict:
    req = finding.requirement
    fact = finding.vendor_fact
    return {
        "category": category,
        "status": "OPEN",
        "requirement_id": req.id,
        "parameter": req.parameter,
        "requirement_text": req.text,
        "finding_status": finding.status.value,
        "confidence": finding.confidence,
        "evaluator_reason": finding.reason,
        "knockout_criterion": req.id in _knockout_ids(report),
        "specification_source": _source_dict(req.source),
        "vendor_evidence": None
        if fact is None
        else {
            "parameter": fact.parameter,
            "raw_value": fact.raw_value,
            "value": fact.value,
            "unit": fact.unit,
            "source": _source_dict(fact.source),
        },
    }


def procurement_review_register(report: ComplianceReport) -> dict:
    deviations = [
        _record(report, finding, "DEVIATION")
        for finding in report.findings
        if finding.status == Status.DEVIATION
    ]
    review_queue = [
        _record(report, finding, "TECHNICAL_REVIEW")
        for finding in report.findings
        if finding.status == Status.REVIEW
    ]
    return {
        "contract": _CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": report.specification,
        "vendor": report.vendor,
        "counts": {
            "deviations": len(deviations),
            "review_queue": len(review_queue),
            "open_items": len(deviations) + len(review_queue),
        },
        "deviations": deviations,
        "review_queue": review_queue,
    }


def procurement_review_portfolio(reports: Iterable[ComplianceReport]) -> dict:
    registers = [procurement_review_register(report) for report in reports]
    return {
        "contract": _PORTFOLIO_CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "vendor_count": len(registers),
        "open_items": sum(item["counts"]["open_items"] for item in registers),
        "registers": registers,
    }


def procurement_review_json(report: ComplianceReport) -> str:
    return json.dumps(procurement_review_register(report), indent=2, ensure_ascii=False) + "\n"


def procurement_review_portfolio_json(reports: Iterable[ComplianceReport]) -> str:
    return json.dumps(procurement_review_portfolio(reports), indent=2, ensure_ascii=False) + "\n"


def write_procurement_review_register(report: ComplianceReport, path: str | Path) -> None:
    Path(path).write_text(procurement_review_json(report), encoding="utf-8")


def write_procurement_review_portfolio(reports: Iterable[ComplianceReport], path: str | Path) -> None:
    Path(path).write_text(procurement_review_portfolio_json(reports), encoding="utf-8")
