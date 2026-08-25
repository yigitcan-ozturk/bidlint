from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__
from .supplier_evidence import evidence_assessment_template
from .supplier_history import validate_history
from .supplier_response import ingest_supplier_response_files

_REVIEW_CONTRACT = "bidlint.supplier-clarification-review"
_EVIDENCE_REVIEW_CONTRACT = "bidlint.supplier-evidence-review"
_HISTORY_CONTRACT = "bidlint.supplier-clarification-history"
_ATTESTATION_CONTRACT = "bidlint.supplier-pilot-attestation"
_ATTESTATION_CONTRACT_VERSION = "1"
_GATE_CONTRACT = "bidlint.supplier-portal-readiness"
_GATE_CONTRACT_VERSION = "1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _require_string(mapping: dict, key: str, *, allow_empty: bool = True) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{key} must not be empty")
    return value


def _require_bool(mapping: dict, key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _read_json_object(path: str | Path, label: str) -> tuple[dict, bytes, Path]:
    source = Path(path)
    data = source.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data, source


def _validate_review(review: dict) -> None:
    if review.get("contract") != _REVIEW_CONTRACT:
        raise ValueError(f"supplier pilot requires {_REVIEW_CONTRACT} buyer review")
    if review.get("contract_version") != "1":
        raise ValueError("unsupported supplier clarification review contract_version")
    if review.get("automatic_acceptance") is not False:
        raise ValueError("supplier clarification review must preserve automatic_acceptance=false")
    if review.get("human_review_required") is not True:
        raise ValueError("supplier clarification review must require human review")
    _require_string(review, "specification", allow_empty=False)
    _require_string(review, "vendor", allow_empty=False)
    items = review.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("supplier clarification review must contain at least one item")


def _validate_evidence_review(evidence_review: dict, review: dict) -> None:
    if evidence_review.get("contract") != _EVIDENCE_REVIEW_CONTRACT:
        raise ValueError(f"supplier pilot requires {_EVIDENCE_REVIEW_CONTRACT} evidence review")
    if evidence_review.get("contract_version") != "1":
        raise ValueError("unsupported supplier evidence review contract_version")
    if evidence_review.get("human_review_only") is not True:
        raise ValueError("supplier evidence review must preserve human_review_only=true")
    if evidence_review.get("affects_evaluator") is not False:
        raise ValueError("supplier evidence review must preserve affects_evaluator=false")
    if evidence_review.get("specification") != review["specification"]:
        raise ValueError("supplier evidence review specification does not match buyer review")
    if evidence_review.get("vendor") != review["vendor"]:
        raise ValueError("supplier evidence review vendor does not match buyer review")

    provenance = evidence_review.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("supplier evidence review provenance must be a JSON object")
    source = provenance.get("supplier_clarification_review")
    if not isinstance(source, dict):
        raise ValueError("supplier evidence review is missing buyer-review provenance")
    if source.get("canonical_sha256") != _canonical_json_sha256(review):
        raise ValueError("supplier evidence review is not bound to the supplied buyer review")

    reviewer = evidence_review.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("supplier evidence review reviewer must be a JSON object")
    _require_string(reviewer, "name")
    _require_string(reviewer, "role")
    _require_string(reviewer, "organization")

    items = evidence_review.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("supplier evidence review must contain at least one item")


def _validate_history_binding(history: dict, review: dict) -> dict:
    if history.get("contract") != _HISTORY_CONTRACT:
        raise ValueError(f"supplier pilot requires {_HISTORY_CONTRACT} history")
    validation = validate_history(history)
    if history.get("specification") != review["specification"]:
        raise ValueError("supplier history specification does not match buyer review")
    if history.get("vendor") != review["vendor"]:
        raise ValueError("supplier history vendor does not match buyer review")

    revisions = history.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise ValueError("supplier history must contain at least one revision")
    active = revisions[-1]
    source = active.get("source_supplier_review")
    if not isinstance(source, dict):
        raise ValueError("active supplier history revision is missing supplier-review provenance")
    if source.get("canonical_sha256") != _canonical_json_sha256(review):
        raise ValueError("active supplier history revision is not bound to the supplied buyer review")
    return validation


def prepare_pilot_return(
    register_path: str | Path,
    response_path: str | Path,
    output_dir: str | Path,
) -> dict:
    output = Path(output_dir)
    if output.exists():
        raise ValueError("pilot output directory already exists")
    output.mkdir(parents=True)

    review = ingest_supplier_response_files(register_path, response_path)
    assessment = evidence_assessment_template(review)

    review_path = output / "buyer-review.json"
    assessment_path = output / "evidence-assessment.json"
    manifest_path = output / "pilot-return-manifest.json"

    review_bytes = (json.dumps(review, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    assessment_bytes = (json.dumps(assessment, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    review_path.write_bytes(review_bytes)
    assessment_path.write_bytes(assessment_bytes)

    manifest = {
        "contract": "bidlint.supplier-pilot-return",
        "contract_version": "1",
        "tool": "bidlint",
        "version": __version__,
        "status": "AWAITING_BUYER_EVIDENCE_ASSESSMENT",
        "specification": review["specification"],
        "vendor": review["vendor"],
        "automatic_acceptance": False,
        "human_review_required": True,
        "artifacts": {
            "buyer_review": {
                "path": review_path.name,
                "canonical_sha256": _canonical_json_sha256(review),
                "byte_sha256": _sha256_bytes(review_bytes),
            },
            "evidence_assessment": {
                "path": assessment_path.name,
                "canonical_sha256": _canonical_json_sha256(assessment),
                "byte_sha256": _sha256_bytes(assessment_bytes),
            },
        },
        "next_action": "complete evidence-assessment.json, validate it, then create or append supplier history",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def pilot_attestation_template(review: dict, evidence_review: dict, history: dict) -> dict:
    _validate_review(review)
    _validate_evidence_review(evidence_review, review)
    _validate_history_binding(history, review)
    return {
        "contract": _ATTESTATION_CONTRACT,
        "contract_version": _ATTESTATION_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "pilot_id": "",
        "source_supplier_review_sha256": _canonical_json_sha256(review),
        "source_supplier_evidence_review_sha256": _canonical_json_sha256(evidence_review),
        "source_supplier_history_sha256": _canonical_json_sha256(history),
        "external_supplier_response_received": False,
        "supplier_completed_without_guided_reentry": False,
        "response_return_channel": "",
        "usability_feedback_recorded": False,
        "usability_feedback_summary": "",
        "revision_occurred": False,
        "reviewer": {
            "name": "",
            "role": "",
            "organization": "",
        },
    }


def _validate_attestation(attestation: dict, review: dict, evidence_review: dict, history: dict) -> None:
    if attestation.get("contract") != _ATTESTATION_CONTRACT:
        raise ValueError(f"supplier pilot gate requires {_ATTESTATION_CONTRACT}")
    if attestation.get("contract_version") != _ATTESTATION_CONTRACT_VERSION:
        raise ValueError("unsupported supplier pilot attestation contract_version")
    _require_string(attestation, "pilot_id")
    _require_string(attestation, "response_return_channel")
    _require_string(attestation, "usability_feedback_summary")
    for key in (
        "external_supplier_response_received",
        "supplier_completed_without_guided_reentry",
        "usability_feedback_recorded",
        "revision_occurred",
    ):
        _require_bool(attestation, key)

    reviewer = attestation.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("supplier pilot attestation reviewer must be a JSON object")
    for key in ("name", "role", "organization"):
        _require_string(reviewer, key)

    expected = {
        "source_supplier_review_sha256": _canonical_json_sha256(review),
        "source_supplier_evidence_review_sha256": _canonical_json_sha256(evidence_review),
        "source_supplier_history_sha256": _canonical_json_sha256(history),
    }
    for key, digest in expected.items():
        if attestation.get(key) != digest:
            raise ValueError(f"{key} does not match supplied pilot artifact")


def evaluate_portal_readiness(review: dict, evidence_review: dict, history: dict, attestation: dict) -> dict:
    _validate_review(review)
    _validate_evidence_review(evidence_review, review)
    history_validation = _validate_history_binding(history, review)
    _validate_attestation(attestation, review, evidence_review, history)

    evidence_items = evidence_review["items"]
    evidence_assessment_complete = all(item.get("overall") != "NOT_ASSESSED" for item in evidence_items)
    evidence_reviewer_named = bool(str(evidence_review["reviewer"].get("name") or "").strip())
    revision_count = int(history_validation["revision_count"])
    revision_requirement_met = not attestation["revision_occurred"] or revision_count >= 2

    checks = [
        {
            "check": "external_supplier_response_received",
            "passed": attestation["external_supplier_response_received"],
        },
        {
            "check": "supplier_completed_without_guided_reentry",
            "passed": attestation["supplier_completed_without_guided_reentry"],
        },
        {
            "check": "response_return_channel_recorded",
            "passed": bool(attestation["response_return_channel"].strip()),
        },
        {
            "check": "buyer_evidence_assessment_complete",
            "passed": evidence_assessment_complete and evidence_reviewer_named,
        },
        {
            "check": "immutable_revision_history_valid",
            "passed": history_validation.get("valid") is True,
        },
        {
            "check": "revision_represented_if_occurred",
            "passed": revision_requirement_met,
        },
        {
            "check": "usability_feedback_recorded",
            "passed": attestation["usability_feedback_recorded"]
            and bool(attestation["usability_feedback_summary"].strip()),
        },
        {
            "check": "pilot_reviewer_named",
            "passed": bool(attestation["reviewer"]["name"].strip()),
        },
    ]
    ready = all(item["passed"] for item in checks)
    return {
        "contract": _GATE_CONTRACT,
        "contract_version": _GATE_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "pilot_id": attestation["pilot_id"],
        "specification": review["specification"],
        "vendor": review["vendor"],
        "ready_for_portal_reconsideration": ready,
        "portal_decision": "RECONSIDER_SCOPE" if ready else "DEFERRED",
        "automatic_portal_approval": False,
        "automatic_acceptance": False,
        "affects_evaluator": False,
        "unresolved_conflict_count": history_validation.get("unresolved_conflict_count", 0),
        "checks": checks,
        "provenance": {
            "supplier_review_sha256": _canonical_json_sha256(review),
            "supplier_evidence_review_sha256": _canonical_json_sha256(evidence_review),
            "supplier_history_sha256": _canonical_json_sha256(history),
            "pilot_attestation_sha256": _canonical_json_sha256(attestation),
        },
    }


def write_pilot_attestation_template(
    review_path: str | Path,
    evidence_review_path: str | Path,
    history_path: str | Path,
    output_path: str | Path,
) -> None:
    review, _, _ = _read_json_object(review_path, "supplier clarification review")
    evidence, _, _ = _read_json_object(evidence_review_path, "supplier evidence review")
    history, _, _ = _read_json_object(history_path, "supplier history")
    template = pilot_attestation_template(review, evidence, history)
    Path(output_path).write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_portal_readiness(
    review_path: str | Path,
    evidence_review_path: str | Path,
    history_path: str | Path,
    attestation_path: str | Path,
    output_path: str | Path,
) -> None:
    review, _, _ = _read_json_object(review_path, "supplier clarification review")
    evidence, _, _ = _read_json_object(evidence_review_path, "supplier evidence review")
    history, _, _ = _read_json_object(history_path, "supplier history")
    attestation, _, _ = _read_json_object(attestation_path, "supplier pilot attestation")
    result = evaluate_portal_readiness(review, evidence, history, attestation)
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
