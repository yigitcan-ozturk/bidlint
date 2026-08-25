import json
from pathlib import Path

import pytest

from bidlint.supplier_evidence_binding import validate_evidence_assessment_with_files
from bidlint.supplier_history import initialize_history
from bidlint.supplier_pilot_attested_files import (
    evaluate_portal_readiness_with_files,
    pilot_attestation_template_with_files,
)
from bidlint.supplier_pilot_cli import main as pilot_main
from bidlint.supplier_pilot_files import prepare_pilot_return_with_evidence_files
from bidlint.supplier_workspace import evaluate_supplier_workspace


def _register() -> dict:
    return {
        "contract": "bidlint.procurement-clarifications",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.2.0.dev0",
        "specification": "317L-rfq.pdf",
        "vendor": "supplier-offer.xlsx",
        "counts": {"bidder_clarifications": 1, "unanswered_requirements": 0, "open_items": 1},
        "bidder_clarifications": [
            {
                "category": "BIDDER_CLARIFICATION",
                "status": "OPEN",
                "requirement_id": "R0001",
                "parameter": "material grade",
                "requirement_text": "Material shall be ASTM A182 F317L",
                "question": "Please confirm the offered material grade and provide traceable evidence.",
                "finding_status": "REVIEW",
                "confidence": 0.8,
                "evaluator_reason": "qualitative designation requires review",
                "specification_source": {"document": "317L-rfq.pdf", "page": 1, "line": None, "section": None},
                "vendor_evidence": None,
            }
        ],
        "unanswered_requirements": [],
    }


def _response() -> dict:
    return {
        "contract": "bidlint.supplier-clarification-response",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.2.0.dev0",
        "source_register_contract": "bidlint.procurement-clarifications",
        "source_register_contract_version": "1",
        "specification": "317L-rfq.pdf",
        "vendor": "supplier-offer.xlsx",
        "responder": {"name": "Frank", "company": "CSM"},
        "response_count": 1,
        "responses": [
            {
                "category": "BIDDER_CLARIFICATION",
                "requirement_id": "R0001",
                "parameter": "material grade",
                "finding_status": "REVIEW",
                "supplier_response": "We confirm ASTM A182 F317L.",
                "offered_value": "ASTM A182 F317L",
                "offered_unit_or_designation": "ASTM A182 F317L",
                "evidence_reference": "MTC-317L.pdf",
                "supplier_comment": "",
            }
        ],
    }


def _prepare_workspace(tmp_path: Path) -> Path:
    register = tmp_path / "register.json"
    response = tmp_path / "response.json"
    certificate = tmp_path / "MTC-317L.pdf"
    evidence_map = tmp_path / "evidence-map.json"
    workspace = tmp_path / "pilot-return"
    register.write_text(json.dumps(_register()), encoding="utf-8")
    response.write_text(json.dumps(_response()), encoding="utf-8")
    certificate.write_bytes(b"exact-certificate-bytes")
    evidence_map.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": certificate.name,
                        "requirement_ids": ["R0001"],
                        "evidence_types": ["certificate"],
                        "note": "supplier returned MTC",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    prepare_pilot_return_with_evidence_files(
        register,
        response,
        workspace,
        evidence_map_path=evidence_map,
    )
    return workspace


def _write_completed_evidence_review(workspace: Path) -> tuple[dict, dict, dict]:
    review = json.loads((workspace / "buyer-review.json").read_text(encoding="utf-8"))
    assessment = json.loads((workspace / "evidence-assessment.json").read_text(encoding="utf-8"))
    evidence_files = json.loads((workspace / "evidence-files.json").read_text(encoding="utf-8"))
    assessment["reviewer"] = {
        "name": "Buyer Engineer",
        "role": "Technical Reviewer",
        "organization": "Buyer",
    }
    item = assessment["items"][0]
    for kind, entry in item["evidence"].items():
        if kind == "certificate":
            entry["required"] = "REQUIRED"
            entry["status"] = "ADEQUATE"
            entry["references"] = ["file:F001"]
        else:
            entry["required"] = "NOT_REQUIRED"
            entry["status"] = "NOT_REQUIRED"
    item["overall"] = "ADEQUATE"
    item["rationale"] = "Certificate reviewed by buyer."
    evidence_files_bytes = (workspace / "evidence-files.json").read_bytes()
    evidence_review = validate_evidence_assessment_with_files(
        review,
        assessment,
        evidence_files,
        evidence_files_bytes=evidence_files_bytes,
        evidence_files_name="evidence-files.json",
    )
    (workspace / "evidence-review.json").write_text(
        json.dumps(evidence_review, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return review, evidence_review, evidence_files


def _write_history(workspace: Path, review: dict, evidence_review: dict) -> dict:
    history = initialize_history(review, revision_id="R1", evidence_review=evidence_review)
    (workspace / "supplier-history.json").write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return history


def _completed_attestation(review: dict, evidence_review: dict, history: dict, evidence_files: dict) -> dict:
    attestation = pilot_attestation_template_with_files(review, evidence_review, history, evidence_files)
    attestation.update(
        {
            "pilot_id": "PILOT-317L-001",
            "external_supplier_response_received": True,
            "supplier_completed_without_guided_reentry": True,
            "response_return_channel": "email",
            "usability_feedback_recorded": True,
            "usability_feedback_summary": "Supplier completed the offline workflow and returned file-backed evidence.",
            "revision_occurred": False,
            "reviewer": {
                "name": "Buyer Engineer",
                "role": "Technical Reviewer",
                "organization": "Buyer",
            },
        }
    )
    return attestation


def test_workspace_status_reports_next_safe_stage(tmp_path: Path):
    workspace = _prepare_workspace(tmp_path)

    status = evaluate_supplier_workspace(workspace)
    assert status["stage"] == "AWAITING_EVIDENCE_REVIEW"
    assert status["artifacts"]["evidence_files"]["present"] is True
    assert "--evidence-files evidence-files.json" in status["next_action"]
    assert status["automatic_acceptance"] is False
    assert status["affects_evaluator"] is False

    review, evidence_review, evidence_files = _write_completed_evidence_review(workspace)
    status = evaluate_supplier_workspace(workspace)
    assert status["stage"] == "AWAITING_HISTORY"

    history = _write_history(workspace, review, evidence_review)
    status = evaluate_supplier_workspace(workspace)
    assert status["stage"] == "AWAITING_ATTESTATION"

    incomplete = pilot_attestation_template_with_files(review, evidence_review, history, evidence_files)
    (workspace / "pilot-attestation.json").write_text(json.dumps(incomplete), encoding="utf-8")
    status = evaluate_supplier_workspace(workspace)
    assert status["stage"] == "ATTESTATION_INCOMPLETE"
    assert "external_supplier_response_received" in status["next_action"]

    attestation = _completed_attestation(review, evidence_review, history, evidence_files)
    (workspace / "pilot-attestation.json").write_text(json.dumps(attestation), encoding="utf-8")
    status = evaluate_supplier_workspace(workspace)
    assert status["stage"] == "AWAITING_PORTAL_GATE"

    portal = evaluate_portal_readiness_with_files(review, evidence_review, history, attestation, evidence_files)
    (workspace / "portal-readiness.json").write_text(json.dumps(portal), encoding="utf-8")
    status = evaluate_supplier_workspace(workspace)
    assert status["stage"] == "PORTAL_GATE_EVALUATED"
    assert status["portal_decision"] == "RECONSIDER_SCOPE"
    assert status["artifacts"]["portal_readiness"]["present"] is True


def test_workspace_status_rejects_tampered_bound_artifact(tmp_path: Path):
    workspace = _prepare_workspace(tmp_path)
    review_path = workspace / "buyer-review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["vendor"] = "tampered-offer.xlsx"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(ValueError, match="buyer_review byte SHA-256"):
        evaluate_supplier_workspace(workspace)


def test_workspace_status_rejects_non_reproducible_portal_result(tmp_path: Path):
    workspace = _prepare_workspace(tmp_path)
    review, evidence_review, evidence_files = _write_completed_evidence_review(workspace)
    history = _write_history(workspace, review, evidence_review)
    attestation = _completed_attestation(review, evidence_review, history, evidence_files)
    (workspace / "pilot-attestation.json").write_text(json.dumps(attestation), encoding="utf-8")
    portal = evaluate_portal_readiness_with_files(review, evidence_review, history, attestation, evidence_files)
    portal["portal_decision"] = "DEFERRED"
    (workspace / "portal-readiness.json").write_text(json.dumps(portal), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match deterministic gate result"):
        evaluate_supplier_workspace(workspace)


def test_workspace_status_cli_writes_contract(tmp_path: Path):
    workspace = _prepare_workspace(tmp_path)
    output = tmp_path / "workspace-status.json"

    assert pilot_main(["status", str(workspace), str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["contract"] == "bidlint.supplier-workspace-status"
    assert payload["stage"] == "AWAITING_EVIDENCE_REVIEW"
