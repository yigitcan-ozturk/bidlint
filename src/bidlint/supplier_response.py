from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__

_RESPONSE_CONTRACT = "bidlint.supplier-clarification-response"
_RESPONSE_CONTRACT_VERSION = "1"
_REGISTER_CONTRACT = "bidlint.procurement-clarifications"
_REVIEW_CONTRACT = "bidlint.supplier-clarification-review"
_REVIEW_CONTRACT_VERSION = "1"

_RESPONSE_FIELDS = (
    "supplier_response",
    "offered_value",
    "offered_unit_or_designation",
    "evidence_reference",
    "supplier_comment",
)


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


def _validate_register(register: dict) -> list[dict]:
    if register.get("contract") != _REGISTER_CONTRACT:
        raise ValueError(f"buyer response ingestion requires {_REGISTER_CONTRACT} input")
    if register.get("contract_version") != "1":
        raise ValueError("unsupported clarification register contract_version")
    if not isinstance(register.get("bidder_clarifications"), list):
        raise ValueError("clarification register is missing bidder_clarifications")
    if not isinstance(register.get("unanswered_requirements"), list):
        raise ValueError("clarification register is missing unanswered_requirements")
    _require_string(register, "specification")
    _require_string(register, "vendor")

    items = register["bidder_clarifications"] + register["unanswered_requirements"]
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("clarification register items must be JSON objects")
        requirement_id = _require_string(item, "requirement_id")
        if requirement_id in seen:
            raise ValueError(f"duplicate requirement_id in clarification register: {requirement_id}")
        seen.add(requirement_id)
        _require_string(item, "category")
        _require_string(item, "parameter")
        _require_string(item, "finding_status")
        _require_string(item, "question")
    return items


def _validate_response(response: dict) -> list[dict]:
    if response.get("contract") != _RESPONSE_CONTRACT:
        raise ValueError(f"supplier response requires {_RESPONSE_CONTRACT} contract")
    if response.get("contract_version") != _RESPONSE_CONTRACT_VERSION:
        raise ValueError("unsupported supplier response contract_version")
    if response.get("source_register_contract") != _REGISTER_CONTRACT:
        raise ValueError("supplier response source_register_contract does not match")
    if response.get("source_register_contract_version") != "1":
        raise ValueError("supplier response source_register_contract_version does not match")
    _require_string(response, "specification")
    _require_string(response, "vendor")
    if "source_register_sha256" in response:
        _require_string(response, "source_register_sha256")

    responder = response.get("responder")
    if not isinstance(responder, dict):
        raise ValueError("supplier response responder must be a JSON object")
    _require_string(responder, "name")
    _require_string(responder, "company")

    responses = response.get("responses")
    if not isinstance(responses, list):
        raise ValueError("supplier response is missing responses")
    if response.get("response_count") != len(responses):
        raise ValueError("supplier response_count does not match responses length")

    seen: set[str] = set()
    for item in responses:
        if not isinstance(item, dict):
            raise ValueError("supplier response items must be JSON objects")
        requirement_id = _require_string(item, "requirement_id")
        if requirement_id in seen:
            raise ValueError(f"duplicate requirement_id in supplier response: {requirement_id}")
        seen.add(requirement_id)
        _require_string(item, "category")
        _require_string(item, "parameter")
        _require_string(item, "finding_status")
        for field in _RESPONSE_FIELDS:
            _require_string(item, field)
    return responses


def ingest_supplier_response(
    register: dict,
    response: dict,
    *,
    register_bytes: bytes | None = None,
    response_bytes: bytes | None = None,
    register_name: str | None = None,
    response_name: str | None = None,
) -> dict:
    register_items = _validate_register(register)
    response_items = _validate_response(response)

    if response["specification"] != register["specification"]:
        raise ValueError("supplier response specification does not match clarification register")
    if response["vendor"] != register["vendor"]:
        raise ValueError("supplier response vendor does not match clarification register")

    register_digest = _canonical_json_sha256(register)
    declared_register_digest = response.get("source_register_sha256")
    if declared_register_digest is not None and declared_register_digest != register_digest:
        raise ValueError("supplier response source_register_sha256 does not match clarification register")

    register_by_id = {item["requirement_id"]: item for item in register_items}
    response_by_id = {item["requirement_id"]: item for item in response_items}
    missing = sorted(set(register_by_id) - set(response_by_id))
    unexpected = sorted(set(response_by_id) - set(register_by_id))
    if missing:
        raise ValueError("supplier response is missing requirement_id(s): " + ", ".join(missing))
    if unexpected:
        raise ValueError("supplier response contains unexpected requirement_id(s): " + ", ".join(unexpected))

    review_items: list[dict] = []
    answered = 0
    evidence_referenced = 0
    for register_item in register_items:
        requirement_id = register_item["requirement_id"]
        supplier_item = response_by_id[requirement_id]
        for field in ("category", "parameter", "finding_status"):
            if supplier_item[field] != register_item[field]:
                raise ValueError(f"supplier response {field} mismatch for {requirement_id}")

        has_response = bool(supplier_item["supplier_response"].strip() or supplier_item["offered_value"].strip())
        has_evidence = bool(supplier_item["evidence_reference"].strip())
        answered += int(has_response)
        evidence_referenced += int(has_evidence)

        review_items.append(
            {
                "requirement_id": requirement_id,
                "category": register_item["category"],
                "parameter": register_item["parameter"],
                "requirement_text": register_item.get("requirement_text"),
                "question": register_item["question"],
                "prior_finding_status": register_item["finding_status"],
                "specification_source": register_item.get("specification_source"),
                "prior_vendor_evidence": register_item.get("vendor_evidence"),
                "supplier_response": supplier_item["supplier_response"],
                "offered_value": supplier_item["offered_value"],
                "offered_unit_or_designation": supplier_item["offered_unit_or_designation"],
                "evidence_reference": supplier_item["evidence_reference"],
                "supplier_comment": supplier_item["supplier_comment"],
                "response_present": has_response,
                "evidence_reference_present": has_evidence,
                "review_status": "PENDING_REVIEW",
                "human_review_required": True,
            }
        )

    provenance = {
        "clarification_register": {
            "name": register_name,
            "canonical_sha256": register_digest,
            "byte_sha256": _sha256_bytes(register_bytes) if register_bytes is not None else None,
            "byte_length": len(register_bytes) if register_bytes is not None else None,
        },
        "supplier_response": {
            "name": response_name,
            "byte_sha256": _sha256_bytes(response_bytes) if response_bytes is not None else None,
            "byte_length": len(response_bytes) if response_bytes is not None else None,
        },
        "source_register_binding": {
            "mechanism": (
                "declared-canonical-sha256"
                if declared_register_digest is not None
                else "structural-metadata-and-item-identity"
            ),
            "response_declared_sha256": declared_register_digest,
            "matches": True,
        },
    }

    return {
        "contract": _REVIEW_CONTRACT,
        "contract_version": _REVIEW_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": register["specification"],
        "vendor": register["vendor"],
        "review_status": "PENDING_REVIEW",
        "automatic_acceptance": False,
        "human_review_required": True,
        "responder": response["responder"],
        "counts": {
            "open_items": len(review_items),
            "responses_present": answered,
            "evidence_references_present": evidence_referenced,
        },
        "provenance": provenance,
        "items": review_items,
    }


def ingest_supplier_response_files(
    register_path: str | Path,
    response_path: str | Path,
) -> dict:
    register_file = Path(register_path)
    response_file = Path(response_path)
    register_bytes = register_file.read_bytes()
    response_bytes = response_file.read_bytes()
    register = json.loads(register_bytes.decode("utf-8"))
    response = json.loads(response_bytes.decode("utf-8"))
    if not isinstance(register, dict):
        raise ValueError("clarification register root must be a JSON object")
    if not isinstance(response, dict):
        raise ValueError("supplier response root must be a JSON object")
    return ingest_supplier_response(
        register,
        response,
        register_bytes=register_bytes,
        response_bytes=response_bytes,
        register_name=register_file.name,
        response_name=response_file.name,
    )


def supplier_review_json(review: dict) -> str:
    return json.dumps(review, indent=2, ensure_ascii=False) + "\n"


def write_supplier_review(
    register_path: str | Path,
    response_path: str | Path,
    output_path: str | Path,
) -> None:
    review = ingest_supplier_response_files(register_path, response_path)
    Path(output_path).write_text(supplier_review_json(review), encoding="utf-8")
