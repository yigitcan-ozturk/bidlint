from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .supplier_pilot import evaluate_portal_readiness, pilot_attestation_template

_FILES_CONTRACT = "bidlint.supplier-evidence-files"


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


def evidence_review_requires_file_manifest(evidence_review: dict) -> bool:
    provenance = evidence_review.get("provenance")
    return isinstance(provenance, dict) and isinstance(provenance.get("supplier_evidence_files"), dict)


def _validate_evidence_files_binding(review: dict, evidence_review: dict, evidence_files: dict) -> str:
    if evidence_files.get("contract") != _FILES_CONTRACT:
        raise ValueError(f"supplier pilot evidence binding requires {_FILES_CONTRACT} manifest")
    if evidence_files.get("contract_version") != "1":
        raise ValueError("unsupported supplier evidence files contract_version")
    if evidence_files.get("specification") != review.get("specification"):
        raise ValueError("supplier evidence files specification does not match buyer review")
    if evidence_files.get("vendor") != review.get("vendor"):
        raise ValueError("supplier evidence files vendor does not match buyer review")
    if evidence_files.get("automatic_acceptance") is not False:
        raise ValueError("supplier evidence files must preserve automatic_acceptance=false")
    if evidence_files.get("human_review_required") is not True:
        raise ValueError("supplier evidence files must preserve human_review_required=true")
    if evidence_files.get("affects_evaluator") is not False:
        raise ValueError("supplier evidence files must preserve affects_evaluator=false")

    files_digest = _canonical_json_sha256(evidence_files)
    provenance = evidence_review.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("supplier evidence review provenance must be a JSON object")
    source = provenance.get("supplier_evidence_files")
    if not isinstance(source, dict):
        raise ValueError("supplier evidence review is missing supplier-evidence-files provenance")
    if source.get("canonical_sha256") != files_digest:
        raise ValueError("supplier evidence review is not bound to the supplied evidence-files manifest")

    validation = evidence_review.get("evidence_file_reference_validation")
    if not isinstance(validation, dict) or validation.get("validated") is not True:
        raise ValueError("supplier evidence review does not contain validated evidence-file references")
    return files_digest


def pilot_attestation_template_with_files(
    review: dict,
    evidence_review: dict,
    history: dict,
    evidence_files: dict,
) -> dict:
    template = pilot_attestation_template(review, evidence_review, history)
    files_digest = _validate_evidence_files_binding(review, evidence_review, evidence_files)
    template["source_supplier_evidence_files_sha256"] = files_digest
    return template


def evaluate_portal_readiness_with_files(
    review: dict,
    evidence_review: dict,
    history: dict,
    attestation: dict,
    evidence_files: dict,
) -> dict:
    files_digest = _validate_evidence_files_binding(review, evidence_review, evidence_files)
    if attestation.get("source_supplier_evidence_files_sha256") != files_digest:
        raise ValueError("source_supplier_evidence_files_sha256 does not match supplied evidence-files manifest")

    result = evaluate_portal_readiness(review, evidence_review, history, attestation)
    result["checks"].append({"check": "supplier_evidence_files_bound", "passed": True})
    result["provenance"]["supplier_evidence_files_sha256"] = files_digest
    return result


def write_pilot_attestation_template_with_files(
    review_path: str | Path,
    evidence_review_path: str | Path,
    history_path: str | Path,
    evidence_files_path: str | Path,
    output_path: str | Path,
) -> None:
    review, _, _ = _read_json_object(review_path, "supplier clarification review")
    evidence_review, _, _ = _read_json_object(evidence_review_path, "supplier evidence review")
    history, _, _ = _read_json_object(history_path, "supplier history")
    evidence_files, _, _ = _read_json_object(evidence_files_path, "supplier evidence files")
    template = pilot_attestation_template_with_files(review, evidence_review, history, evidence_files)
    Path(output_path).write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_portal_readiness_with_files(
    review_path: str | Path,
    evidence_review_path: str | Path,
    history_path: str | Path,
    attestation_path: str | Path,
    evidence_files_path: str | Path,
    output_path: str | Path,
) -> None:
    review, _, _ = _read_json_object(review_path, "supplier clarification review")
    evidence_review, _, _ = _read_json_object(evidence_review_path, "supplier evidence review")
    history, _, _ = _read_json_object(history_path, "supplier history")
    attestation, _, _ = _read_json_object(attestation_path, "supplier pilot attestation")
    evidence_files, _, _ = _read_json_object(evidence_files_path, "supplier evidence files")
    result = evaluate_portal_readiness_with_files(review, evidence_review, history, attestation, evidence_files)
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
