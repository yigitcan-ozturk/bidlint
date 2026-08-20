from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from . import __version__
from .models import ComplianceReport, KnockoutStatus

_CONTRACT = "bidlint.procurement-readiness"
_PORTFOLIO_CONTRACT = "bidlint.procurement-readiness-portfolio"
_CONTRACT_VERSION = "1"

READY = "READY"
ACTION_REQUIRED = "ACTION_REQUIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
POLICY_REQUIRED = "POLICY_REQUIRED"
DISQUALIFIED = "DISQUALIFIED"


def procurement_status(report: ComplianceReport) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not report.findings:
        return ACTION_REQUIRED, ["report contains no technical requirements"]

    if report.knockout is None:
        return POLICY_REQUIRED, ["explicit knockout policy has not been applied"]

    if report.knockout.status == KnockoutStatus.DISQUALIFIED:
        failed = ", ".join(report.knockout.failed_requirement_ids)
        reasons.append(
            "failed knockout requirement(s): " + failed
            if failed
            else "knockout gate is disqualified"
        )
        return DISQUALIFIED, reasons

    if report.knockout.status == KnockoutStatus.REVIEW_REQUIRED:
        review_ids = ", ".join(report.knockout.review_requirement_ids)
        reasons.append(
            "knockout review required for: " + review_ids
            if review_ids
            else "knockout gate requires review"
        )
        return REVIEW_REQUIRED, reasons

    counts = report.counts
    if counts["REVIEW"]:
        reasons.append(f"{counts['REVIEW']} technical finding(s) require review")
        return REVIEW_REQUIRED, reasons
    if counts["DEVIATION"] or counts["MISSING"]:
        if counts["DEVIATION"]:
            reasons.append(f"{counts['DEVIATION']} deviation(s) remain open")
        if counts["MISSING"]:
            reasons.append(f"{counts['MISSING']} requirement(s) remain unanswered")
        return ACTION_REQUIRED, reasons
    return READY, []


def procurement_readiness(report: ComplianceReport) -> dict:
    status, reasons = procurement_status(report)
    return {
        "contract": _CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": report.specification,
        "vendor": report.vendor,
        "status": status,
        "reasons": reasons,
        "compliance_score": report.compliance_score,
        "counts": report.counts,
        "knockout_status": report.knockout.status.value if report.knockout else None,
    }


def procurement_portfolio(reports: Iterable[ComplianceReport]) -> dict:
    reports = list(reports)
    entries = [procurement_readiness(report) for report in reports]
    ready_by_vendor = {
        entry["vendor"]: entry
        for entry in entries
        if entry["status"] == READY
    }
    ready_reports = [
        report for report in reports
        if report.vendor in ready_by_vendor
    ]
    ranked_ready = sorted(
        ready_reports,
        key=lambda report: (
            -report.compliance_score,
            report.counts["DEVIATION"] + report.counts["MISSING"],
            report.counts["REVIEW"],
            report.vendor.lower(),
        ),
    )
    ready_ranking = [
        {
            "rank": index,
            **ready_by_vendor[report.vendor],
        }
        for index, report in enumerate(ranked_ready, start=1)
    ]
    excluded = [
        entry
        for entry in entries
        if entry["status"] != READY
    ]
    return {
        "contract": _PORTFOLIO_CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "vendor_count": len(entries),
        "ready_count": len(ready_ranking),
        "excluded_count": len(excluded),
        "ready_ranking": ready_ranking,
        "excluded": excluded,
    }


def procurement_json(report: ComplianceReport) -> str:
    return json.dumps(procurement_readiness(report), indent=2, ensure_ascii=False) + "\n"


def procurement_portfolio_json(reports: Iterable[ComplianceReport]) -> str:
    return json.dumps(procurement_portfolio(reports), indent=2, ensure_ascii=False) + "\n"


def write_procurement_readiness(report: ComplianceReport, path: str | Path) -> None:
    Path(path).write_text(procurement_json(report), encoding="utf-8")


def write_procurement_portfolio(reports: Iterable[ComplianceReport], path: str | Path) -> None:
    Path(path).write_text(procurement_portfolio_json(reports), encoding="utf-8")
