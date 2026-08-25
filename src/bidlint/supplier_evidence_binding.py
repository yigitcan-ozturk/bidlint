from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .supplier_evidence import validate_evidence_assessment

_FILES_CONTRACT = "bidlint.supplier-evidence-files"
_EVIDENCE_TYPES = {"calculation", "certificate", "test_basis", "supporting_document"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _read_json_object(path: str | Path, label: str) -> tuple[dict, bytes, Path]:
    source = Path(path)
    data = source.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data, source


def _iter_file_references(assessment: dict):
    items = assessment.get("items")
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        requirement_id = item.get("requirement_id")
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            continue
        for kind, entry in evidence.items():
            if not isinstance(entry, dict):
                continue
            references = entry.get("references")
            if not isinstance(references, list):
                continue
            for reference in references:
                if isinstance(reference, str) and reference.startswith("file:"):
                    yield requirement_id, kind, reference


def assessment_contains_file_references(assessment_path: str | Path) -> bool:
    assessment, _, _ = _read_json_object(assessment_path, "supplier evidence assessment")
    return any(True for _ in _iter_file_references(assessment))


def _validate_file_manifest(manifest: dict, review: dict) -> dict[str, dict]:
    if manifest.get("contract") != _FILES_CONTRACT:
        raise ValueError(f"evidence file binding requires {_FILES_CONTRACT} manifest")
    if manifest.get("contract_version") != "1":
        raise ValueError("unsupported supplier evidence files contract_version")
    if manifest.get("automatic_acceptance") is not False:
        raise ValueError("supplier evidence files must preserve automatic_acceptance=false")
    if manifest.get("human_review_required") is not True:
        raise ValueError("supplier evidence files must preserve human_review_required=true")
    if manifest.get("affects_evaluator") is not False:
        raise ValueError("supplier evidence files must preserve affects_evaluator=false")
    if manifest.get("specification") != review.get("specification"):
        raise ValueError("supplier evidence files specification does not match buyer review")
    if manifest.get("vendor") != review.get("vendor"):
        raise ValueError("supplier evidence files vendor does not match buyer review")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("supplier evidence files provenance must be a JSON object")
    source = provenance.get("supplier_clarification_review")
    if not isinstance(source, dict) or source.get("canonical_sha256") != _canonical_json_sha256(review):
        raise ValueError("supplier evidence files are not bound to the supplied buyer review")

    valid_ids = {item.get("requirement_id") for item in review.get("items", []) if isinstance(item, dict)}
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("supplier evidence files manifest must contain at least one file")
    by_reference: dict[str, dict] = {}
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("supplier evidence files entries must be JSON objects")
        file_id = item.get("file_id")
        reference = item.get("reference")
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("supplier evidence file_id must be a non-empty string")
        if reference != f"file:{file_id}":
            raise ValueError(f"supplier evidence reference does not match file_id {file_id}")
        if reference in by_reference:
            raise ValueError(f"duplicate supplier evidence file reference: {reference}")
        digest = item.get("byte_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"invalid byte_sha256 for {reference}")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError(f"invalid byte_sha256 for {reference}") from exc
        if not isinstance(item.get("byte_length"), int) or item["byte_length"] < 0:
            raise ValueError(f"invalid byte_length for {reference}")
        requirement_ids = item.get("requirement_ids")
        if not isinstance(requirement_ids, list) or not requirement_ids:
            raise ValueError(f"requirement_ids for {reference} must be a non-empty list")
        unknown = sorted(set(requirement_ids) - valid_ids)
        if unknown:
            raise ValueError(f"unknown requirement_id in {reference}: " + ", ".join(unknown))
        evidence_types = item.get("evidence_types")
        if not isinstance(evidence_types, list) or not evidence_types:
            raise ValueError(f"evidence_types for {reference} must be a non-empty list")
        invalid_types = sorted(set(evidence_types) - _EVIDENCE_TYPES)
        if invalid_types:
            raise ValueError(f"unsupported evidence_type in {reference}: " + ", ".join(invalid_types))
        by_reference[reference] = item
    return by_reference


def validate_evidence_assessment_with_files(
    review: dict,
    assessment: dict,
    evidence_files: dict,
    *,
    review_bytes: bytes | None = None,
    assessment_bytes: bytes | None = None,
    evidence_files_bytes: bytes | None = None,
    review_name: str | None = None,
    assessment_name: str | None = None,
    evidence_files_name: str | None = None,
) -> dict:
    validated = validate_evidence_assessment(
        review,
        assessment,
        review_bytes=review_bytes,
        assessment_bytes=assessment_bytes,
        review_name=review_name,
        assessment_name=assessment_name,
    )
    by_reference = _validate_file_manifest(evidence_files, review)

    referenced: set[str] = set()
    for requirement_id, kind, reference in _iter_file_references(assessment):
        file_entry = by_reference.get(reference)
        if file_entry is None:
            raise ValueError(f"unknown supplier evidence file reference: {reference}")
        if requirement_id not in file_entry["requirement_ids"]:
            raise ValueError(f"{reference} is not bound to requirement {requirement_id}")
        if kind not in file_entry["evidence_types"]:
            raise ValueError(f"{reference} is not bound to evidence type {kind}")
        referenced.add(reference)

    validated["provenance"]["supplier_evidence_files"] = {
        "name": evidence_files_name,
        "canonical_sha256": _canonical_json_sha256(evidence_files),
        "byte_sha256": _sha256_bytes(evidence_files_bytes) if evidence_files_bytes is not None else None,
        "byte_length": len(evidence_files_bytes) if evidence_files_bytes is not None else None,
    }
    validated["evidence_file_reference_validation"] = {
        "validated": True,
        "referenced_file_count": len(referenced),
        "referenced_files": sorted(referenced),
    }
    return validated


def write_validated_evidence_review_with_files(
    review_path: str | Path,
    assessment_path: str | Path,
    evidence_files_path: str | Path,
    output_path: str | Path,
) -> None:
    review, review_bytes, review_file = _read_json_object(review_path, "supplier clarification review")
    assessment, assessment_bytes, assessment_file = _read_json_object(
        assessment_path, "supplier evidence assessment"
    )
    evidence_files, evidence_files_bytes, evidence_files_file = _read_json_object(
        evidence_files_path, "supplier evidence files"
    )
    validated = validate_evidence_assessment_with_files(
        review,
        assessment,
        evidence_files,
        review_bytes=review_bytes,
        assessment_bytes=assessment_bytes,
        evidence_files_bytes=evidence_files_bytes,
        review_name=review_file.name,
        assessment_name=assessment_file.name,
        evidence_files_name=evidence_files_file.name,
    )
    Path(output_path).write_text(json.dumps(validated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
