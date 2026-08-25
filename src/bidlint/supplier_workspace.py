from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__
from .supplier_pilot import (
    _validate_evidence_review,
    _validate_history_binding,
    _validate_review,
    evaluate_portal_readiness,
)
from .supplier_pilot_attested_files import (
    _validate_evidence_files_binding,
    evidence_review_requires_file_manifest,
    evaluate_portal_readiness_with_files,
)

_STATUS_CONTRACT = "bidlint.supplier-workspace-status"
_STATUS_CONTRACT_VERSION = "1"
_PILOT_RETURN_CONTRACT = "bidlint.supplier-pilot-return"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _read_json(path: Path, label: str) -> tuple[dict, bytes]:
    data = path.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data


def _safe_workspace_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} path must be a non-empty string")
    candidate = Path(value)
    if candidate.is_absolute() or candidate.name != value or ".." in candidate.parts:
        raise ValueError(f"{label} path must be a workspace-local basename")
    return root / candidate


def _verify_manifest_artifact(root: Path, descriptor: dict, label: str) -> tuple[dict, bytes, Path]:
    if not isinstance(descriptor, dict):
        raise ValueError(f"pilot-return manifest {label} descriptor must be a JSON object")
    path = _safe_workspace_file(root, descriptor.get("path"), label)
    if not path.is_file():
        raise ValueError(f"pilot workspace is missing {label}: {path.name}")
    payload, data = _read_json(path, label)
    expected_byte = descriptor.get("byte_sha256")
    if expected_byte is not None and expected_byte != _sha256_bytes(data):
        raise ValueError(f"{label} byte SHA-256 does not match pilot-return manifest")
    expected_canonical = descriptor.get("canonical_sha256")
    if expected_canonical is not None and expected_canonical != _canonical_json_sha256(payload):
        raise ValueError(f"{label} canonical SHA-256 does not match pilot-return manifest")
    return payload, data, path


def _optional_json(root: Path, name: str, label: str) -> tuple[dict, bytes, Path] | None:
    path = root / name
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {name}")
    payload, data = _read_json(path, label)
    return payload, data, path


def evaluate_supplier_workspace(workspace_dir: str | Path) -> dict:
    root = Path(workspace_dir)
    if not root.is_dir():
        raise ValueError("supplier pilot workspace must be an existing directory")

    pilot_manifest_path = root / "pilot-return-manifest.json"
    if not pilot_manifest_path.is_file():
        raise ValueError("supplier pilot workspace is missing pilot-return-manifest.json")
    pilot_manifest, pilot_manifest_bytes = _read_json(pilot_manifest_path, "pilot-return manifest")
    if pilot_manifest.get("contract") != _PILOT_RETURN_CONTRACT:
        raise ValueError(f"supplier workspace requires {_PILOT_RETURN_CONTRACT} manifest")
    if pilot_manifest.get("contract_version") != "1":
        raise ValueError("unsupported supplier pilot-return contract_version")
    artifacts = pilot_manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("pilot-return manifest artifacts must be a JSON object")

    review, review_bytes, review_path = _verify_manifest_artifact(root, artifacts.get("buyer_review"), "buyer_review")
    assessment, assessment_bytes, assessment_path = _verify_manifest_artifact(
        root, artifacts.get("evidence_assessment"), "evidence_assessment"
    )
    _validate_review(review)

    evidence_files = None
    evidence_files_bytes = None
    evidence_files_path = None
    if "evidence_files" in artifacts:
        evidence_files, evidence_files_bytes, evidence_files_path = _verify_manifest_artifact(
            root, artifacts["evidence_files"], "evidence_files"
        )
        _validate_evidence_files_binding(
            review,
            {
                "provenance": {
                    "supplier_evidence_files": {
                        "canonical_sha256": _canonical_json_sha256(evidence_files)
                    }
                },
                "evidence_file_reference_validation": {"validated": True},
            },
            evidence_files,
        )

    checks: list[dict] = [
        {"check": "pilot_return_manifest_valid", "passed": True},
        {"check": "buyer_review_bound", "passed": True},
        {"check": "evidence_assessment_bound", "passed": True},
    ]
    artifact_status = {
        "pilot_return_manifest": {
            "present": True,
            "name": pilot_manifest_path.name,
            "byte_sha256": _sha256_bytes(pilot_manifest_bytes),
        },
        "buyer_review": {
            "present": True,
            "name": review_path.name,
            "canonical_sha256": _canonical_json_sha256(review),
            "byte_sha256": _sha256_bytes(review_bytes),
        },
        "evidence_assessment": {
            "present": True,
            "name": assessment_path.name,
            "canonical_sha256": _canonical_json_sha256(assessment),
            "byte_sha256": _sha256_bytes(assessment_bytes),
        },
        "evidence_files": {
            "present": evidence_files is not None,
            "name": evidence_files_path.name if evidence_files_path else None,
            "canonical_sha256": _canonical_json_sha256(evidence_files) if evidence_files is not None else None,
            "byte_sha256": _sha256_bytes(evidence_files_bytes) if evidence_files_bytes is not None else None,
        },
    }
    if evidence_files is not None:
        checks.append({"check": "evidence_files_bound", "passed": True})

    evidence_review_entry = _optional_json(root, "evidence-review.json", "supplier evidence review")
    history_entry = _optional_json(root, "supplier-history.json", "supplier history")
    attestation_entry = _optional_json(root, "pilot-attestation.json", "supplier pilot attestation")
    portal_entry = _optional_json(root, "portal-readiness.json", "supplier portal readiness")

    stage = "AWAITING_EVIDENCE_REVIEW"
    next_action = (
        "complete evidence-assessment.json and validate it to evidence-review.json"
        + (" using --evidence-files evidence-files.json" if evidence_files is not None else "")
    )
    portal_decision = None

    evidence_review = None
    history = None
    attestation = None
    expected_gate = None

    if evidence_review_entry is not None:
        evidence_review, evidence_review_bytes, evidence_review_path = evidence_review_entry
        _validate_evidence_review(evidence_review, review)
        file_backed = evidence_review_requires_file_manifest(evidence_review)
        if file_backed:
            if evidence_files is None:
                raise ValueError("file-backed evidence review requires evidence-files.json in pilot workspace")
            _validate_evidence_files_binding(review, evidence_review, evidence_files)
        elif evidence_files is not None:
            checks.append({"check": "evidence_files_referenced_by_review", "passed": False, "blocking": False})
        evidence_complete = all(
            isinstance(item, dict) and item.get("overall") != "NOT_ASSESSED"
            for item in evidence_review.get("items", [])
        ) and bool(str(evidence_review.get("reviewer", {}).get("name") or "").strip())
        artifact_status["evidence_review"] = {
            "present": True,
            "name": evidence_review_path.name,
            "canonical_sha256": _canonical_json_sha256(evidence_review),
            "byte_sha256": _sha256_bytes(evidence_review_bytes),
            "complete": evidence_complete,
        }
        checks.append({"check": "evidence_review_bound", "passed": True})
        if evidence_complete:
            stage = "AWAITING_HISTORY"
            next_action = "create supplier-history.json with the reviewed supplier revision"
        else:
            stage = "EVIDENCE_REVIEW_INCOMPLETE"
            next_action = "complete all evidence-review items and name the human reviewer"

    if history_entry is not None:
        if evidence_review is None:
            raise ValueError("supplier-history.json requires evidence-review.json in pilot workspace")
        history, history_bytes, history_path = history_entry
        history_validation = _validate_history_binding(history, review)
        artifact_status["supplier_history"] = {
            "present": True,
            "name": history_path.name,
            "canonical_sha256": _canonical_json_sha256(history),
            "byte_sha256": _sha256_bytes(history_bytes),
            "revision_count": history_validation.get("revision_count"),
            "unresolved_conflict_count": history_validation.get("unresolved_conflict_count", 0),
        }
        checks.append({"check": "supplier_history_valid", "passed": history_validation.get("valid") is True})
        stage = "AWAITING_ATTESTATION"
        next_action = (
            "create pilot-attestation.json with bidlint-supplier-pilot attestation-template"
            + (" --evidence-files evidence-files.json" if evidence_review_requires_file_manifest(evidence_review) else "")
        )

    if attestation_entry is not None:
        if evidence_review is None or history is None:
            raise ValueError("pilot-attestation.json requires evidence-review.json and supplier-history.json")
        attestation, attestation_bytes, attestation_path = attestation_entry
        if evidence_review_requires_file_manifest(evidence_review):
            if evidence_files is None:
                raise ValueError("file-backed pilot attestation requires evidence-files.json")
            expected_gate = evaluate_portal_readiness_with_files(
                review, evidence_review, history, attestation, evidence_files
            )
        else:
            expected_gate = evaluate_portal_readiness(review, evidence_review, history, attestation)
        artifact_status["pilot_attestation"] = {
            "present": True,
            "name": attestation_path.name,
            "canonical_sha256": _canonical_json_sha256(attestation),
            "byte_sha256": _sha256_bytes(attestation_bytes),
        }
        checks.append({"check": "pilot_attestation_bound", "passed": True})
        if expected_gate["ready_for_portal_reconsideration"]:
            stage = "AWAITING_PORTAL_GATE"
            next_action = (
                "run bidlint-supplier-pilot portal-gate to portal-readiness.json"
                + (" with --evidence-files evidence-files.json" if evidence_review_requires_file_manifest(evidence_review) else "")
            )
        else:
            stage = "ATTESTATION_INCOMPLETE"
            failed = [check["check"] for check in expected_gate["checks"] if not check["passed"]]
            next_action = "complete pilot attestation requirements: " + ", ".join(failed)

    if portal_entry is not None:
        if expected_gate is None:
            raise ValueError("portal-readiness.json requires a valid pilot-attestation.json")
        portal, portal_bytes, portal_path = portal_entry
        if portal != expected_gate:
            raise ValueError("portal-readiness.json does not match deterministic gate result for workspace artifacts")
        artifact_status["portal_readiness"] = {
            "present": True,
            "name": portal_path.name,
            "canonical_sha256": _canonical_json_sha256(portal),
            "byte_sha256": _sha256_bytes(portal_bytes),
        }
        checks.append({"check": "portal_readiness_reproducible", "passed": True})
        stage = "PORTAL_GATE_EVALUATED"
        portal_decision = portal.get("portal_decision")
        next_action = (
            "revisit hosted portal product scope" if portal_decision == "RECONSIDER_SCOPE" else "keep hosted portal scope deferred"
        )

    for name in ("evidence_review", "supplier_history", "pilot_attestation", "portal_readiness"):
        artifact_status.setdefault(name, {"present": False, "name": None})

    return {
        "contract": _STATUS_CONTRACT,
        "contract_version": _STATUS_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "specification": review["specification"],
        "vendor": review["vendor"],
        "stage": stage,
        "next_action": next_action,
        "portal_decision": portal_decision,
        "automatic_acceptance": False,
        "automatic_portal_approval": False,
        "human_review_required": True,
        "affects_evaluator": False,
        "checks": checks,
        "artifacts": artifact_status,
    }


def write_supplier_workspace_status(workspace_dir: str | Path, output_path: str | Path) -> dict:
    result = evaluate_supplier_workspace(workspace_dir)
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
