from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .models import ComplianceReport, Status

_CONTRACT = "supplier-scorecard.technical-compliance"
_CONTRACT_VERSION = "1"


def supplier_scorecard_signal(report: ComplianceReport, supplier: str) -> dict:
    """Build a supplier-scorecard profile fragment from one bidlint report.

    Contract v1 predates procurement knockout gates. Knockout-assessed reports
    are rejected rather than silently exporting a technically disqualified or
    review-blocked supplier as an ordinary READY score.
    """
    if not isinstance(supplier, str) or not supplier.strip():
        raise ValueError("supplier name is required")
    if report.knockout is not None:
        raise ValueError("supplier-scorecard contract v1 does not support knockout-assessed reports")

    counts = report.counts
    review_ids = [
        finding.requirement.id
        for finding in report.findings
        if finding.status == Status.REVIEW
    ]
    if not report.findings:
        status = "NO_REQUIREMENTS"
        technical_compliance = None
    elif review_ids:
        status = "REVIEW_REQUIRED"
        technical_compliance = None
    else:
        status = "READY"
        technical_compliance = report.compliance_score

    return {
        "contract": _CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "supplier": supplier.strip(),
        "technical_compliance": technical_compliance,
        "technical_compliance_status": status,
        "technical_compliance_audit": {
            "tool": "bidlint",
            "version": __version__,
            "specification": report.specification,
            "vendor": report.vendor,
            "compliance_score": report.compliance_score,
            "counts": counts,
            "finding_count": len(report.findings),
            "review_requirement_ids": review_ids,
        },
    }


def supplier_scorecard_json(report: ComplianceReport, supplier: str) -> str:
    return json.dumps(supplier_scorecard_signal(report, supplier), indent=2, ensure_ascii=False) + "\n"


def write_supplier_scorecard_signal(report: ComplianceReport, supplier: str, path: str | Path) -> None:
    Path(path).write_text(supplier_scorecard_json(report, supplier), encoding="utf-8")
