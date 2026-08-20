from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .models import ComplianceReport, Status
from .procurement import READY, procurement_status

_CONTRACT = "supplier-scorecard.technical-compliance"
_CONTRACT_VERSION = "1"
_PROCUREMENT_CONTRACT_VERSION = "2"


def supplier_scorecard_signal(report: ComplianceReport, supplier: str) -> dict:
    """Build the backward-compatible supplier-scorecard v1 fragment."""
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


def supplier_scorecard_signal_v2(report: ComplianceReport, supplier: str) -> dict:
    """Build a procurement-aware supplier-scorecard v2 fragment.

    Numeric technical compliance is published only for procurement READY
    suppliers. Other states retain the raw score inside the audit payload
    without exposing it as an automatic ranking signal.
    """
    if not isinstance(supplier, str) or not supplier.strip():
        raise ValueError("supplier name is required")

    readiness, reasons = procurement_status(report)
    technical_compliance = report.compliance_score if readiness == READY else None
    return {
        "contract": _CONTRACT,
        "contract_version": _PROCUREMENT_CONTRACT_VERSION,
        "supplier": supplier.strip(),
        "technical_compliance": technical_compliance,
        "technical_compliance_status": readiness,
        "technical_compliance_audit": {
            "tool": "bidlint",
            "version": __version__,
            "specification": report.specification,
            "vendor": report.vendor,
            "compliance_score": report.compliance_score,
            "counts": report.counts,
            "finding_count": len(report.findings),
            "knockout_status": report.knockout.status.value if report.knockout else None,
            "procurement_reasons": reasons,
        },
    }


def supplier_scorecard_json(report: ComplianceReport, supplier: str) -> str:
    return json.dumps(supplier_scorecard_signal(report, supplier), indent=2, ensure_ascii=False) + "\n"


def supplier_scorecard_json_v2(report: ComplianceReport, supplier: str) -> str:
    return json.dumps(supplier_scorecard_signal_v2(report, supplier), indent=2, ensure_ascii=False) + "\n"


def write_supplier_scorecard_signal(report: ComplianceReport, supplier: str, path: str | Path) -> None:
    Path(path).write_text(supplier_scorecard_json(report, supplier), encoding="utf-8")


def write_supplier_scorecard_signal_v2(report: ComplianceReport, supplier: str, path: str | Path) -> None:
    Path(path).write_text(supplier_scorecard_json_v2(report, supplier), encoding="utf-8")
