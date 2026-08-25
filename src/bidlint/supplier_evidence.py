from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__

_BUYER_REVIEW_CONTRACT = "bidlint.supplier-clarification-review"
_ASSESSMENT_CONTRACT = "bidlint.supplier-evidence-assessment"
_ASSESSMENT_CONTRACT_VERSION = "1"
_EVIDENCE_REVIEW_CONTRACT = "bidlint.supplier-evidence-review"
_EVIDENCE_REVIEW_CONTRACT_VERSION = "1"

_EVIDENCE_TYPES = ("calculation", "certificate", "test_basis", "supporting_document")
_REQUIRED_VALUES = {"UNKNOWN", "REQUIRED", "NOT_REQUIRED"}
_EVIDENCE_STATUS_VALUES = {"NOT_ASSESSED", "MISSING", "PARTIAL", "ADEQUATE", "NOT_REQUIRED"}
_OVERALL_VALUES = {"NOT_ASSESSED", "INADEQUATE", "PARTIAL", "ADEQUATE", "NEEDS_CLARIFICATION"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _require_string(mapping: dict, key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _validate_buyer_review(review: dict) -> list[dict]:
    if review.get("contract") != _BUYER_REVIEW_CONTRACT:
        raise ValueError(f"evidence assessment requires {_BUYER_REVIEW_CONTRACT} input")
    if review.get("contract_version") != "1":
        raise ValueError("unsupported supplier clarification review contract_version")
    if review.get("automatic_acceptance") is not False:
        raise ValueError("supplier clarification review must preserve automatic_acceptance=false")
    if review.get("human_review_required") is not True:
        raise ValueError("supplier clarification review must require human review")
    _require_string(review, "specification")
    _require_string(review, "vendor")

    items = review.get("items")
    if not isinstance(items, list):
        raise ValueError("supplier clarification review is missing items")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("supplier clarification review items must be JSON objects")
        requirement_id = _require_string(item, "requirement_id")
        if requirement_id in seen:
            raise ValueError(f"duplicate requirement_id in supplier clarification review: {requirement_id}")
        seen.add(requirement_id)
        _require_string(item, "parameter")
        _require_string(item, "prior_finding_status")
    return items


def _blank_evidence_entry() -> dict:
    return {
        "required": "UNKNOWN",
        "status": "NOT_ASSESSED",
        "references": [],
        "note": "",
    }


def evidence_assessment_template(review: dict) -> dict:
    items = _validate_buyer_review(review)
    source_digest = _canonical_json_sha256(review)
    return {
        "contract": _ASSESSMENT_CONTRACT,
        "contract_version": _ASSESSMENT_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "source_supplier_review_sha256": source_digest,
        "specification": review["specification"],
        "vendor": review["vendor"],
        "reviewer": {
            "name": "",
            "role": "",
            "organization": "",
        },
        "items": [
            {
                "requirement_id": item["requirement_id"],
                "parameter": item["parameter"],
                "prior_finding_status": item["prior_finding_status"],
                "evidence": {kind: _blank_evidence_entry() for kind in _EVIDENCE_TYPES},
                "overall": "NOT_ASSESSED",
                "rationale": "",
            }
            for item in items
        ],
    }


def _validate_evidence_entry(requirement_id: str, kind: str, entry: object) -> dict:
    if not isinstance(entry, dict):
        raise ValueError(f"{kind} evidence entry for {requirement_id} must be a JSON object")

    required = _require_string(entry, "required")
    status = _require_string(entry, "status")
    if required not in _REQUIRED_VALUES:
        raise ValueError(f"invalid required value for {requirement_id}/{kind}: {required}")
    if status not in _EVIDENCE_STATUS_VALUES:
        raise ValueError(f"invalid evidence status for {requirement_id}/{kind}: {status}")

    references = entry.get("references")
    if not isinstance(references, list) or not all(isinstance(value, str) for value in references):
        raise ValueError(f"references for {requirement_id}/{kind} must be a list of strings")
    note = _require_string(entry, "note")

    if required == "UNKNOWN" and status != "NOT_ASSESSED":
        raise ValueError(f"{requirement_id}/{kind} must stay NOT_ASSESSED while required is UNKNOWN")
    if required == "NOT_REQUIRED" and status != "NOT_REQUIRED":
        raise ValueError(f"{requirement_id}/{kind} must use NOT_REQUIRED status when evidence is not required")
    if status == "NOT_REQUIRED" and required != "NOT_REQUIRED":
        raise ValueError(f"{requirement_id}/{kind} NOT_REQUIRED status requires required=NOT_REQUIRED")
    if required == "REQUIRED" and status == "NOT_REQUIRED":
        raise ValueError(f"{requirement_id}/{kind} required evidence cannot be marked NOT_REQUIRED")
    if status in {"PARTIAL", "ADEQUATE"} and not any(value.strip() for value in references):
        raise ValueError(f"{requirement_id}/{kind} {status} status requires at least one evidence reference")

    return {
        "required": required,
        "status": status,
        "references": references,
        "note": note,
    }


def _validate_assessment(review: dict, assessment: dict) -> list[dict]:
    review_items = _validate_buyer_review(review)
    if assessment.get("contract") != _ASSESSMENT_CONTRACT:
        raise ValueError(f"evidence assessment requires {_ASSESSMENT_CONTRACT} contract")
    if assessment.get("contract_version") != _ASSESSMENT_CONTRACT_VERSION:
        raise ValueError("unsupported supplier evidence assessment contract_version")
    if assessment.get("source_supplier_review_sha256") != _canonical_json_sha256(review):
        raise ValueError("source_supplier_review_sha256 does not match supplier clarification review")
    if assessment.get("specification") != review["specification"]:
        raise ValueError("evidence assessment specification does not match supplier clarification review")
    if assessment.get("vendor") != review["vendor"]:
        raise ValueError("evidence assessment vendor does not match supplier clarification review")

    reviewer = assessment.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("evidence assessment reviewer must be a JSON object")
    for key in ("name", "role", "organization"):
        _require_string(reviewer, key)

    assessed_items = assessment.get("items")
    if not isinstance(assessed_items, list):
        raise ValueError("evidence assessment is missing items")

    review_by_id = {item["requirement_id"]: item for item in review_items}
    assessed_by_id: dict[str, dict] = {}
    for item in assessed_items:
        if not isinstance(item, dict):
            raise ValueError("evidence assessment items must be JSON objects")
        requirement_id = _require_string(item, "requirement_id")
        if requirement_id in assessed_by_id:
            raise ValueError(f"duplicate requirement_id in evidence assessment: {requirement_id}")
        assessed_by_id[requirement_id] = item

    missing = sorted(set(review_by_id) - set(assessed_by_id))
    unexpected = sorted(set(assessed_by_id) - set(review_by_id))
    if missing:
        raise ValueError("evidence assessment is missing requirement_id(s): " + ", ".join(missing))
    if unexpected:
        raise ValueError("evidence assessment contains unexpected requirement_id(s): " + ", ".join(unexpected))

    normalized: list[dict] = []
    for review_item in review_items:
        requirement_id = review_item["requirement_id"]
        item = assessed_by_id[requirement_id]
        if _require_string(item, "parameter") != review_item["parameter"]:
            raise ValueError(f"evidence assessment parameter mismatch for {requirement_id}")
        if _require_string(item, "prior_finding_status") != review_item["prior_finding_status"]:
            raise ValueError(f"evidence assessment prior_finding_status mismatch for {requirement_id}")

        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            raise ValueError(f"evidence assessment evidence for {requirement_id} must be a JSON object")
        if set(evidence) != set(_EVIDENCE_TYPES):
            raise ValueError(
                f"evidence assessment for {requirement_id} must contain exactly: "
                + ", ".join(_EVIDENCE_TYPES)
            )
        normalized_evidence = {
            kind: _validate_evidence_entry(requirement_id, kind, evidence[kind]) for kind in _EVIDENCE_TYPES
        }

        overall = _require_string(item, "overall")
        if overall not in _OVERALL_VALUES:
            raise ValueError(f"invalid overall evidence status for {requirement_id}: {overall}")
        rationale = _require_string(item, "rationale")

        required_statuses = [
            entry["status"] for entry in normalized_evidence.values() if entry["required"] == "REQUIRED"
        ]
        if overall == "ADEQUATE" and any(status != "ADEQUATE" for status in required_statuses):
            raise ValueError(f"{requirement_id} cannot be ADEQUATE while required evidence is not ADEQUATE")
        if overall == "ADEQUATE" and any(
            entry["required"] == "UNKNOWN" for entry in normalized_evidence.values()
        ):
            raise ValueError(f"{requirement_id} cannot be ADEQUATE while evidence requirements are UNKNOWN")

        normalized.append(
            {
                "requirement_id": requirement_id,
                "parameter": review_item["parameter"],
                "prior_finding_status": review_item["prior_finding_status"],
                "evidence": normalized_evidence,
                "overall": overall,
                "rationale": rationale,
            }
        )
    return normalized


def validate_evidence_assessment(
    review: dict,
    assessment: dict,
    *,
    review_bytes: bytes | None = None,
    assessment_bytes: bytes | None = None,
    review_name: str | None = None,
    assessment_name: str | None = None,
) -> dict:
    items = _validate_assessment(review, assessment)
    counts = {status: 0 for status in sorted(_OVERALL_VALUES)}
    for item in items:
        counts[item["overall"]] += 1

    return {
        "contract": _EVIDENCE_REVIEW_CONTRACT,
        "contract_version": _EVIDENCE_REVIEW_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": review["specification"],
        "vendor": review["vendor"],
        "human_review_only": True,
        "affects_evaluator": False,
        "reviewer": assessment["reviewer"],
        "counts": counts,
        "provenance": {
            "supplier_clarification_review": {
                "name": review_name,
                "canonical_sha256": _canonical_json_sha256(review),
                "byte_sha256": _sha256_bytes(review_bytes) if review_bytes is not None else None,
                "byte_length": len(review_bytes) if review_bytes is not None else None,
            },
            "supplier_evidence_assessment": {
                "name": assessment_name,
                "byte_sha256": _sha256_bytes(assessment_bytes) if assessment_bytes is not None else None,
                "byte_length": len(assessment_bytes) if assessment_bytes is not None else None,
            },
        },
        "items": items,
    }


def _read_json_object(path: str | Path, label: str) -> tuple[dict, bytes, Path]:
    source = Path(path)
    data = source.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data, source


def write_evidence_assessment_template(review_path: str | Path, output_path: str | Path) -> None:
    review, _, _ = _read_json_object(review_path, "supplier clarification review")
    template = evidence_assessment_template(review)
    Path(output_path).write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_validated_evidence_review(
    review_path: str | Path,
    assessment_path: str | Path,
    output_path: str | Path,
) -> None:
    review, review_bytes, review_file = _read_json_object(review_path, "supplier clarification review")
    assessment, assessment_bytes, assessment_file = _read_json_object(
        assessment_path,
        "supplier evidence assessment",
    )
    validated = validate_evidence_assessment(
        review,
        assessment,
        review_bytes=review_bytes,
        assessment_bytes=assessment_bytes,
        review_name=review_file.name,
        assessment_name=assessment_file.name,
    )
    Path(output_path).write_text(json.dumps(validated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
