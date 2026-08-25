from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import __version__

_REVIEW_CONTRACT = "bidlint.supplier-clarification-review"
_EVIDENCE_REVIEW_CONTRACT = "bidlint.supplier-evidence-review"
_HISTORY_CONTRACT = "bidlint.supplier-clarification-history"
_HISTORY_CONTRACT_VERSION = "1"
_VALIDATION_CONTRACT = "bidlint.supplier-clarification-history-validation"
_VALIDATION_CONTRACT_VERSION = "1"

_CORE_CONFLICT_FIELDS = ("offered_value", "offered_unit_or_designation")
_TRACKED_FIELDS = (
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


def _require_string(mapping: dict, key: str, *, allow_empty: bool = True) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{key} must not be empty")
    return value


def _validate_review(review: dict) -> list[dict]:
    if review.get("contract") != _REVIEW_CONTRACT:
        raise ValueError(f"supplier history requires {_REVIEW_CONTRACT} input")
    if review.get("contract_version") != "1":
        raise ValueError("unsupported supplier clarification review contract_version")
    if review.get("automatic_acceptance") is not False:
        raise ValueError("supplier clarification review must preserve automatic_acceptance=false")
    if review.get("human_review_required") is not True:
        raise ValueError("supplier clarification review must require human review")
    _require_string(review, "specification", allow_empty=False)
    _require_string(review, "vendor", allow_empty=False)
    responder = review.get("responder")
    if not isinstance(responder, dict):
        raise ValueError("supplier clarification review responder must be a JSON object")
    _require_string(responder, "name")
    _require_string(responder, "company")

    items = review.get("items")
    if not isinstance(items, list):
        raise ValueError("supplier clarification review is missing items")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("supplier clarification review items must be JSON objects")
        requirement_id = _require_string(item, "requirement_id", allow_empty=False)
        if requirement_id in seen:
            raise ValueError(f"duplicate requirement_id in supplier clarification review: {requirement_id}")
        seen.add(requirement_id)
        _require_string(item, "parameter", allow_empty=False)
        _require_string(item, "prior_finding_status", allow_empty=False)
        for field in _TRACKED_FIELDS:
            _require_string(item, field)
    return items


def _validate_evidence_review(evidence_review: dict, review: dict) -> None:
    if evidence_review.get("contract") != _EVIDENCE_REVIEW_CONTRACT:
        raise ValueError(f"supplier history evidence input requires {_EVIDENCE_REVIEW_CONTRACT}")
    if evidence_review.get("contract_version") != "1":
        raise ValueError("unsupported supplier evidence review contract_version")
    if evidence_review.get("human_review_only") is not True:
        raise ValueError("supplier evidence review must preserve human_review_only=true")
    if evidence_review.get("affects_evaluator") is not False:
        raise ValueError("supplier evidence review must preserve affects_evaluator=false")
    if evidence_review.get("specification") != review["specification"]:
        raise ValueError("supplier evidence review specification does not match supplier clarification review")
    if evidence_review.get("vendor") != review["vendor"]:
        raise ValueError("supplier evidence review vendor does not match supplier clarification review")

    provenance = evidence_review.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("supplier evidence review provenance must be a JSON object")
    source = provenance.get("supplier_clarification_review")
    if not isinstance(source, dict):
        raise ValueError("supplier evidence review is missing supplier clarification review provenance")
    if source.get("canonical_sha256") != _canonical_json_sha256(review):
        raise ValueError("supplier evidence review is not bound to the supplied clarification review")


def _snapshot_items(review_items: list[dict], evidence_review: dict | None) -> list[dict]:
    evidence_by_id: dict[str, dict] = {}
    if evidence_review is not None:
        evidence_items = evidence_review.get("items")
        if not isinstance(evidence_items, list):
            raise ValueError("supplier evidence review is missing items")
        for evidence_item in evidence_items:
            if not isinstance(evidence_item, dict):
                raise ValueError("supplier evidence review items must be JSON objects")
            requirement_id = _require_string(evidence_item, "requirement_id", allow_empty=False)
            if requirement_id in evidence_by_id:
                raise ValueError(f"duplicate requirement_id in supplier evidence review: {requirement_id}")
            evidence_by_id[requirement_id] = evidence_item
        review_ids = {item["requirement_id"] for item in review_items}
        if set(evidence_by_id) != review_ids:
            missing = sorted(review_ids - set(evidence_by_id))
            unexpected = sorted(set(evidence_by_id) - review_ids)
            if missing:
                raise ValueError("supplier evidence review is missing requirement_id(s): " + ", ".join(missing))
            raise ValueError("supplier evidence review contains unexpected requirement_id(s): " + ", ".join(unexpected))

    snapshots: list[dict] = []
    for item in review_items:
        requirement_id = item["requirement_id"]
        evidence_item = evidence_by_id.get(requirement_id)
        snapshots.append(
            {
                "requirement_id": requirement_id,
                "parameter": item["parameter"],
                "prior_finding_status": item["prior_finding_status"],
                "supplier_response": item["supplier_response"],
                "offered_value": item["offered_value"],
                "offered_unit_or_designation": item["offered_unit_or_designation"],
                "evidence_reference": item["evidence_reference"],
                "supplier_comment": item["supplier_comment"],
                "evidence_overall": evidence_item.get("overall") if evidence_item is not None else None,
                "evidence": copy.deepcopy(evidence_item.get("evidence")) if evidence_item is not None else None,
            }
        )
    return snapshots


def _field_conflicts(previous: dict, current: dict) -> list[str]:
    conflicts: list[str] = []
    for field in _CORE_CONFLICT_FIELDS:
        old = str(previous.get(field) or "").strip()
        new = str(current.get(field) or "").strip()
        if old and new and old != new:
            conflicts.append(field)
    if previous.get("parameter") != current.get("parameter"):
        conflicts.append("parameter")
    if previous.get("prior_finding_status") != current.get("prior_finding_status"):
        conflicts.append("prior_finding_status")
    return conflicts


def _compare_items(previous_items: list[dict], current_items: list[dict]) -> tuple[list[dict], list[dict]]:
    previous_by_id = {item["requirement_id"]: item for item in previous_items}
    current_by_id = {item["requirement_id"]: item for item in current_items}
    requirement_ids = sorted(set(previous_by_id) | set(current_by_id))
    changes: list[dict] = []
    conflicts: list[dict] = []

    for requirement_id in requirement_ids:
        previous = previous_by_id.get(requirement_id)
        current = current_by_id.get(requirement_id)
        if previous is None:
            changes.append({"requirement_id": requirement_id, "change": "ADDED", "changed_fields": []})
            continue
        if current is None:
            changes.append({"requirement_id": requirement_id, "change": "REMOVED", "changed_fields": []})
            continue

        changed_fields = [
            field
            for field in ("parameter", "prior_finding_status", *_TRACKED_FIELDS, "evidence_overall", "evidence")
            if previous.get(field) != current.get(field)
        ]
        conflict_fields = _field_conflicts(previous, current)
        if conflict_fields:
            change = "CONFLICT"
            conflicts.append(
                {
                    "requirement_id": requirement_id,
                    "fields": conflict_fields,
                    "previous": {field: previous.get(field) for field in conflict_fields},
                    "current": {field: current.get(field) for field in conflict_fields},
                    "resolution_status": "PENDING_REVIEW",
                }
            )
        elif changed_fields:
            change = "CHANGED"
        else:
            change = "UNCHANGED"
        changes.append(
            {
                "requirement_id": requirement_id,
                "change": change,
                "changed_fields": changed_fields,
            }
        )
    return changes, conflicts


def _revision_payload_without_digest(revision: dict) -> dict:
    payload = copy.deepcopy(revision)
    payload.pop("revision_sha256", None)
    return payload


def _revision_digest(revision: dict) -> str:
    return _canonical_json_sha256(_revision_payload_without_digest(revision))


def _validate_history(history: dict) -> None:
    if history.get("contract") != _HISTORY_CONTRACT:
        raise ValueError(f"supplier history requires {_HISTORY_CONTRACT} contract")
    if history.get("contract_version") != _HISTORY_CONTRACT_VERSION:
        raise ValueError("unsupported supplier clarification history contract_version")
    _require_string(history, "specification", allow_empty=False)
    _require_string(history, "vendor", allow_empty=False)
    active_revision_id = _require_string(history, "active_revision_id", allow_empty=False)
    revisions = history.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise ValueError("supplier clarification history must contain at least one revision")

    seen_ids: set[str] = set()
    previous_revision: dict | None = None
    for expected_sequence, revision in enumerate(revisions, start=1):
        if not isinstance(revision, dict):
            raise ValueError("supplier clarification history revisions must be JSON objects")
        revision_id = _require_string(revision, "revision_id", allow_empty=False)
        if revision_id in seen_ids:
            raise ValueError(f"duplicate revision_id in supplier clarification history: {revision_id}")
        seen_ids.add(revision_id)
        if revision.get("sequence") != expected_sequence:
            raise ValueError(f"invalid sequence for revision {revision_id}")
        expected_parent_id = previous_revision["revision_id"] if previous_revision is not None else None
        expected_parent_digest = previous_revision["revision_sha256"] if previous_revision is not None else None
        if revision.get("supersedes_revision_id") != expected_parent_id:
            raise ValueError(f"invalid supersedes_revision_id for revision {revision_id}")
        if revision.get("parent_revision_sha256") != expected_parent_digest:
            raise ValueError(f"invalid parent_revision_sha256 for revision {revision_id}")
        if revision.get("revision_sha256") != _revision_digest(revision):
            raise ValueError(f"revision_sha256 mismatch for revision {revision_id}")
        previous_revision = revision

    if previous_revision is None or active_revision_id != previous_revision["revision_id"]:
        raise ValueError("active_revision_id does not match the latest revision")
    if history.get("active_revision_sha256") != previous_revision["revision_sha256"]:
        raise ValueError("active_revision_sha256 does not match the latest revision")


def _source_record(payload: dict, data: bytes | None, name: str | None) -> dict:
    return {
        "name": name,
        "canonical_sha256": _canonical_json_sha256(payload),
        "byte_sha256": _sha256_bytes(data) if data is not None else None,
        "byte_length": len(data) if data is not None else None,
    }


def _build_revision(
    review: dict,
    review_items: list[dict],
    *,
    revision_id: str,
    sequence: int,
    supersedes_revision_id: str | None,
    parent_revision_sha256: str | None,
    previous_items: list[dict] | None,
    review_bytes: bytes | None,
    review_name: str | None,
    evidence_review: dict | None,
    evidence_bytes: bytes | None,
    evidence_name: str | None,
) -> tuple[dict, list[dict]]:
    snapshots = _snapshot_items(review_items, evidence_review)
    if previous_items is None:
        changes = [
            {"requirement_id": item["requirement_id"], "change": "ADDED", "changed_fields": []}
            for item in snapshots
        ]
        conflicts: list[dict] = []
    else:
        changes, conflicts = _compare_items(previous_items, snapshots)

    revision = {
        "revision_id": revision_id,
        "sequence": sequence,
        "supersedes_revision_id": supersedes_revision_id,
        "parent_revision_sha256": parent_revision_sha256,
        "source_supplier_review": _source_record(review, review_bytes, review_name),
        "source_supplier_evidence_review": (
            _source_record(evidence_review, evidence_bytes, evidence_name) if evidence_review is not None else None
        ),
        "responder": copy.deepcopy(review["responder"]),
        "changes_from_previous": changes,
        "conflict_count": len(conflicts),
        "items": snapshots,
    }
    revision["revision_sha256"] = _revision_digest(revision)
    return revision, conflicts


def initialize_history(
    review: dict,
    *,
    revision_id: str,
    review_bytes: bytes | None = None,
    review_name: str | None = None,
    evidence_review: dict | None = None,
    evidence_bytes: bytes | None = None,
    evidence_name: str | None = None,
) -> dict:
    revision_id = revision_id.strip()
    if not revision_id:
        raise ValueError("revision_id must not be empty")
    review_items = _validate_review(review)
    if evidence_review is not None:
        _validate_evidence_review(evidence_review, review)
    revision, conflicts = _build_revision(
        review,
        review_items,
        revision_id=revision_id,
        sequence=1,
        supersedes_revision_id=None,
        parent_revision_sha256=None,
        previous_items=None,
        review_bytes=review_bytes,
        review_name=review_name,
        evidence_review=evidence_review,
        evidence_bytes=evidence_bytes,
        evidence_name=evidence_name,
    )
    return {
        "contract": _HISTORY_CONTRACT,
        "contract_version": _HISTORY_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": review["specification"],
        "vendor": review["vendor"],
        "human_review_only": True,
        "affects_evaluator": False,
        "active_revision_id": revision_id,
        "active_revision_sha256": revision["revision_sha256"],
        "revision_count": 1,
        "unresolved_conflict_count": len(conflicts),
        "conflicts": conflicts,
        "revisions": [revision],
    }


def append_history(
    history: dict,
    review: dict,
    *,
    revision_id: str,
    supersedes_revision_id: str,
    review_bytes: bytes | None = None,
    review_name: str | None = None,
    evidence_review: dict | None = None,
    evidence_bytes: bytes | None = None,
    evidence_name: str | None = None,
) -> dict:
    _validate_history(history)
    revision_id = revision_id.strip()
    supersedes_revision_id = supersedes_revision_id.strip()
    if not revision_id:
        raise ValueError("revision_id must not be empty")
    if not supersedes_revision_id:
        raise ValueError("supersedes_revision_id must not be empty")
    existing_ids = {revision["revision_id"] for revision in history["revisions"]}
    if revision_id in existing_ids:
        raise ValueError(f"revision_id already exists: {revision_id}")
    if supersedes_revision_id != history["active_revision_id"]:
        raise ValueError(
            "supersedes_revision_id must match the active revision; branching revisions require explicit human resolution"
        )

    review_items = _validate_review(review)
    if review["specification"] != history["specification"]:
        raise ValueError("supplier clarification review specification does not match history")
    if review["vendor"] != history["vendor"]:
        raise ValueError("supplier clarification review vendor does not match history")
    if evidence_review is not None:
        _validate_evidence_review(evidence_review, review)

    previous_revision = history["revisions"][-1]
    revision, conflicts = _build_revision(
        review,
        review_items,
        revision_id=revision_id,
        sequence=len(history["revisions"]) + 1,
        supersedes_revision_id=previous_revision["revision_id"],
        parent_revision_sha256=previous_revision["revision_sha256"],
        previous_items=previous_revision["items"],
        review_bytes=review_bytes,
        review_name=review_name,
        evidence_review=evidence_review,
        evidence_bytes=evidence_bytes,
        evidence_name=evidence_name,
    )

    result = copy.deepcopy(history)
    result["version"] = __version__
    result["revisions"].append(revision)
    result["active_revision_id"] = revision_id
    result["active_revision_sha256"] = revision["revision_sha256"]
    result["revision_count"] = len(result["revisions"])
    result["conflicts"] = conflicts
    result["unresolved_conflict_count"] = len(conflicts)
    _validate_history(result)
    return result


def validate_history(history: dict) -> dict:
    _validate_history(history)
    return {
        "contract": _VALIDATION_CONTRACT,
        "contract_version": _VALIDATION_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "valid": True,
        "specification": history["specification"],
        "vendor": history["vendor"],
        "revision_count": len(history["revisions"]),
        "active_revision_id": history["active_revision_id"],
        "active_revision_sha256": history["active_revision_sha256"],
        "unresolved_conflict_count": history.get("unresolved_conflict_count", 0),
    }


def _read_json_object(path: str | Path, label: str) -> tuple[dict, bytes, Path]:
    source = Path(path)
    data = source.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data, source


def _optional_evidence(path: str | Path | None) -> tuple[dict | None, bytes | None, Path | None]:
    if path is None:
        return None, None, None
    return _read_json_object(path, "supplier evidence review")


def write_initialized_history(
    review_path: str | Path,
    output_path: str | Path,
    *,
    revision_id: str,
    evidence_review_path: str | Path | None = None,
) -> None:
    review, review_bytes, review_file = _read_json_object(review_path, "supplier clarification review")
    evidence, evidence_bytes, evidence_file = _optional_evidence(evidence_review_path)
    history = initialize_history(
        review,
        revision_id=revision_id,
        review_bytes=review_bytes,
        review_name=review_file.name,
        evidence_review=evidence,
        evidence_bytes=evidence_bytes,
        evidence_name=evidence_file.name if evidence_file is not None else None,
    )
    Path(output_path).write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_appended_history(
    history_path: str | Path,
    review_path: str | Path,
    output_path: str | Path,
    *,
    revision_id: str,
    supersedes_revision_id: str,
    evidence_review_path: str | Path | None = None,
) -> None:
    history, _, _ = _read_json_object(history_path, "supplier clarification history")
    review, review_bytes, review_file = _read_json_object(review_path, "supplier clarification review")
    evidence, evidence_bytes, evidence_file = _optional_evidence(evidence_review_path)
    updated = append_history(
        history,
        review,
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
        review_bytes=review_bytes,
        review_name=review_file.name,
        evidence_review=evidence,
        evidence_bytes=evidence_bytes,
        evidence_name=evidence_file.name if evidence_file is not None else None,
    )
    Path(output_path).write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_history_validation(history_path: str | Path, output_path: str | Path) -> None:
    history, _, _ = _read_json_object(history_path, "supplier clarification history")
    result = validate_history(history)
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
