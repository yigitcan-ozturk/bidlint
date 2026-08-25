from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path

from . import __version__

_REVIEW_CONTRACT = "bidlint.supplier-clarification-review"
_MANIFEST_CONTRACT = "bidlint.supplier-evidence-files"
_MANIFEST_CONTRACT_VERSION = "1"
_EVIDENCE_TYPES = {"calculation", "certificate", "test_basis", "supporting_document"}


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


def _validate_review(review: dict) -> set[str]:
    if review.get("contract") != _REVIEW_CONTRACT:
        raise ValueError(f"supplier evidence files require {_REVIEW_CONTRACT} buyer review")
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
    requirement_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("supplier clarification review items must be JSON objects")
        requirement_id = _require_string(item, "requirement_id", allow_empty=False)
        if requirement_id in requirement_ids:
            raise ValueError(f"duplicate requirement_id in supplier clarification review: {requirement_id}")
        requirement_ids.add(requirement_id)
    return requirement_ids


def _read_json_object(path: str | Path, label: str) -> tuple[dict, bytes, Path]:
    source = Path(path)
    data = source.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data, source


def build_supplier_evidence_file_manifest(
    review: dict,
    evidence_map: dict,
    *,
    evidence_map_dir: str | Path,
    review_bytes: bytes | None = None,
    review_name: str | None = None,
    evidence_map_bytes: bytes | None = None,
    evidence_map_name: str | None = None,
) -> dict:
    valid_requirement_ids = _validate_review(review)
    entries = evidence_map.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("evidence map must contain a non-empty files list")

    root = Path(evidence_map_dir)
    seen_paths: set[Path] = set()
    seen_names: set[str] = set()
    files: list[dict] = []

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError("evidence map files must be JSON objects")
        raw_path = _require_string(entry, "path", allow_empty=False)
        source = Path(raw_path)
        if not source.is_absolute():
            source = root / source
        resolved = source.resolve()
        if resolved in seen_paths:
            raise ValueError(f"duplicate evidence source path: {raw_path}")
        seen_paths.add(resolved)
        if not resolved.exists():
            raise ValueError(f"evidence file does not exist: {raw_path}")
        if not resolved.is_file():
            raise ValueError(f"evidence path is not a file: {raw_path}")

        name = resolved.name
        if name in seen_names:
            raise ValueError(f"duplicate evidence basename is ambiguous: {name}")
        seen_names.add(name)

        requirement_ids = entry.get("requirement_ids")
        if not isinstance(requirement_ids, list) or not requirement_ids:
            raise ValueError(f"requirement_ids for {name} must be a non-empty list")
        if not all(isinstance(value, str) and value.strip() for value in requirement_ids):
            raise ValueError(f"requirement_ids for {name} must contain non-empty strings")
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError(f"duplicate requirement_id binding for {name}")
        unknown = sorted(set(requirement_ids) - valid_requirement_ids)
        if unknown:
            raise ValueError(f"unknown requirement_id binding for {name}: " + ", ".join(unknown))

        evidence_types = entry.get("evidence_types")
        if not isinstance(evidence_types, list) or not evidence_types:
            raise ValueError(f"evidence_types for {name} must be a non-empty list")
        if not all(isinstance(value, str) for value in evidence_types):
            raise ValueError(f"evidence_types for {name} must contain strings")
        if len(set(evidence_types)) != len(evidence_types):
            raise ValueError(f"duplicate evidence_type binding for {name}")
        invalid_types = sorted(set(evidence_types) - _EVIDENCE_TYPES)
        if invalid_types:
            raise ValueError(f"unsupported evidence_type for {name}: " + ", ".join(invalid_types))

        note = _require_string(entry, "note")
        data = resolved.read_bytes()
        file_id = f"F{index:03d}"
        media_type, _ = mimetypes.guess_type(name)
        files.append(
            {
                "file_id": file_id,
                "reference": f"file:{file_id}",
                "name": name,
                "byte_sha256": _sha256_bytes(data),
                "byte_length": len(data),
                "media_type": media_type,
                "requirement_ids": requirement_ids,
                "evidence_types": evidence_types,
                "note": note,
            }
        )

    return {
        "contract": _MANIFEST_CONTRACT,
        "contract_version": _MANIFEST_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": review["specification"],
        "vendor": review["vendor"],
        "automatic_acceptance": False,
        "human_review_required": True,
        "affects_evaluator": False,
        "content_interpreted": False,
        "files_copied": False,
        "file_count": len(files),
        "provenance": {
            "supplier_clarification_review": {
                "name": review_name,
                "canonical_sha256": _canonical_json_sha256(review),
                "byte_sha256": _sha256_bytes(review_bytes) if review_bytes is not None else None,
                "byte_length": len(review_bytes) if review_bytes is not None else None,
            },
            "evidence_map": {
                "name": evidence_map_name,
                "byte_sha256": _sha256_bytes(evidence_map_bytes) if evidence_map_bytes is not None else None,
                "byte_length": len(evidence_map_bytes) if evidence_map_bytes is not None else None,
            },
        },
        "files": files,
    }


def write_supplier_evidence_file_manifest(
    review_path: str | Path,
    evidence_map_path: str | Path,
    output_path: str | Path,
) -> dict:
    review, review_bytes, review_file = _read_json_object(review_path, "supplier clarification review")
    evidence_map, evidence_map_bytes, evidence_map_file = _read_json_object(evidence_map_path, "evidence map")
    manifest = build_supplier_evidence_file_manifest(
        review,
        evidence_map,
        evidence_map_dir=evidence_map_file.parent,
        review_bytes=review_bytes,
        review_name=review_file.name,
        evidence_map_bytes=evidence_map_bytes,
        evidence_map_name=evidence_map_file.name,
    )
    Path(output_path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
