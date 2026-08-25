from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .supplier_response import ingest_supplier_response_files

_READINESS_CONTRACT = "bidlint.supplier-response-readiness"
_READINESS_CONTRACT_VERSION = "1"


def evaluate_supplier_response_readiness_files(
    register_path: str | Path,
    response_path: str | Path,
) -> dict:
    review = ingest_supplier_response_files(register_path, response_path)

    responder = review["responder"]
    counts = review["counts"]
    items = review["items"]
    binding = review["provenance"]["source_register_binding"]

    unanswered_ids = [item["requirement_id"] for item in items if not item["response_present"]]
    missing_evidence_ids = [item["requirement_id"] for item in items if not item["evidence_reference_present"]]

    checks = [
        {
            "check": "responder_name_present",
            "passed": bool(str(responder.get("name") or "").strip()),
            "blocking": True,
        },
        {
            "check": "responder_company_present",
            "passed": bool(str(responder.get("company") or "").strip()),
            "blocking": True,
        },
        {
            "check": "source_register_binding_verified",
            "passed": binding.get("matches") is True,
            "blocking": True,
        },
        {
            "check": "all_open_items_answered",
            "passed": counts["responses_present"] == counts["open_items"],
            "blocking": True,
        },
        {
            "check": "evidence_reference_coverage_complete",
            "passed": counts["evidence_references_present"] == counts["open_items"],
            "blocking": False,
        },
    ]

    blocking_failures = [check["check"] for check in checks if check["blocking"] and not check["passed"]]
    ready = not blocking_failures

    return {
        "contract": _READINESS_CONTRACT,
        "contract_version": _READINESS_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": review["specification"],
        "vendor": review["vendor"],
        "ready_for_buyer_review": ready,
        "automatic_acceptance": False,
        "human_review_required": True,
        "affects_evaluator": False,
        "counts": {
            "open_items": counts["open_items"],
            "responses_present": counts["responses_present"],
            "evidence_references_present": counts["evidence_references_present"],
            "unanswered_items": len(unanswered_ids),
            "items_without_evidence_reference": len(missing_evidence_ids),
        },
        "unanswered_requirement_ids": unanswered_ids,
        "missing_evidence_reference_requirement_ids": missing_evidence_ids,
        "blocking_failures": blocking_failures,
        "checks": checks,
        "provenance": review["provenance"],
    }


def write_supplier_response_readiness(
    register_path: str | Path,
    response_path: str | Path,
    output_path: str | Path,
) -> dict:
    result = evaluate_supplier_response_readiness_files(register_path, response_path)
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
