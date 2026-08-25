import json
from pathlib import Path

import pytest

from bidlint.supplier_evidence import evidence_assessment_template, validate_evidence_assessment
from bidlint.supplier_history import initialize_history
from bidlint.supplier_pilot import (
    evaluate_portal_readiness,
    pilot_attestation_template,
    prepare_pilot_return,
)


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
                "question": "Please confirm the offered material grade.",
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
                "evidence_reference": "MTC-001",
                "supplier_comment": "",
            }
        ],
    }


def _review() -> dict:
    return {
        "contract": "bidlint.supplier-clarification-review",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.2.0.dev0",
        "specification": "317L-rfq.pdf",
        "vendor": "supplier-offer.xlsx",
        "review_status": "PENDING_REVIEW",
        "automatic_acceptance": False,
        "human_review_required": True,
        "responder": {"name": "Frank", "company": "CSM"},
        "counts": {"open_items": 1, "responses_present": 1, "evidence_references_present": 1},
        "provenance": {},
        "items": [
            {
                "requirement_id": "R0001",
                "category": "BIDDER_CLARIFICATION",
                "parameter": "material grade",
                "requirement_text": "Material shall be ASTM A182 F317L",
                "question": "Please confirm the offered material grade.",
                "prior_finding_status": "REVIEW",
                "specification_source": None,
                "prior_vendor_evidence": None,
                "supplier_response": "We confirm ASTM A182 F317L.",
                "offered_value": "ASTM A182 F317L",
                "offered_unit_or_designation": "ASTM A182 F317L",
                "evidence_reference": "MTC-001",
                "supplier_comment": "",
                "response_present": True,
                "evidence_reference_present": True,
                "review_status": "PENDING_REVIEW",
                "human_review_required": True,
            }
        ],
    }


def _evidence_review(review: dict) -> dict:
    assessment = evidence_assessment_template(review)
    assessment["reviewer"] = {"name": "Buyer Engineer", "role": "Technical Reviewer", "organization": "Buyer"}
    item = assessment["items"][0]
    for evidence in item["evidence"].values():
        evidence["required"] = "NOT_REQUIRED"
        evidence["status"] = "NOT_REQUIRED"
    item["overall"] = "ADEQUATE"
    item["rationale"] = "Supplier confirmation reviewed; no additional evidence class required for this pilot item."
    return validate_evidence_assessment(review, assessment)


def _completed_attestation(review: dict, evidence_review: dict, history: dict) -> dict:
    attestation = pilot_attestation_template(review, evidence_review, history)
    attestation.update(
        {
            "pilot_id": "PILOT-317L-001",
            "external_supplier_response_received": True,
            "supplier_completed_without_guided_reentry": True,
            "response_return_channel": "email",
            "usability_feedback_recorded": True,
            "usability_feedback_summary": "Supplier completed and returned the structured response without re-entry support.",
            "revision_occurred": False,
            "reviewer": {"name": "Buyer Engineer", "role": "Technical Reviewer", "organization": "Buyer"},
        }
    )
    return attestation


def test_prepare_pilot_return_creates_buyer_artifacts(tmp_path: Path):
    register = tmp_path / "register.json"
    response = tmp_path / "response.json"
    output = tmp_path / "pilot-return"
    register.write_text(json.dumps(_register()), encoding="utf-8")
    response.write_text(json.dumps(_response()), encoding="utf-8")

    manifest = prepare_pilot_return(register, response, output)

    assert manifest["status"] == "AWAITING_BUYER_EVIDENCE_ASSESSMENT"
    assert manifest["automatic_acceptance"] is False
    assert (output / "buyer-review.json").exists()
    assert (output / "evidence-assessment.json").exists()
    assert (output / "pilot-return-manifest.json").exists()


def test_prepare_pilot_return_refuses_existing_directory(tmp_path: Path):
    register = tmp_path / "register.json"
    response = tmp_path / "response.json"
    output = tmp_path / "pilot-return"
    register.write_text(json.dumps(_register()), encoding="utf-8")
    response.write_text(json.dumps(_response()), encoding="utf-8")
    output.mkdir()

    with pytest.raises(ValueError, match="already exists"):
        prepare_pilot_return(register, response, output)


def test_portal_gate_stays_deferred_when_real_interaction_attestation_is_incomplete():
    review = _review()
    evidence = _evidence_review(review)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence)
    attestation = pilot_attestation_template(review, evidence, history)

    result = evaluate_portal_readiness(review, evidence, history, attestation)

    assert result["ready_for_portal_reconsideration"] is False
    assert result["portal_decision"] == "DEFERRED"
    assert result["automatic_portal_approval"] is False
    assert result["affects_evaluator"] is False


def test_portal_gate_allows_reconsideration_after_complete_external_pilot():
    review = _review()
    evidence = _evidence_review(review)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence)
    attestation = _completed_attestation(review, evidence, history)

    result = evaluate_portal_readiness(review, evidence, history, attestation)

    assert result["ready_for_portal_reconsideration"] is True
    assert result["portal_decision"] == "RECONSIDER_SCOPE"
    assert result["automatic_portal_approval"] is False
    assert all(check["passed"] for check in result["checks"])


def test_portal_gate_requires_revision_history_when_attested_revision_occurred():
    review = _review()
    evidence = _evidence_review(review)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence)
    attestation = _completed_attestation(review, evidence, history)
    attestation["revision_occurred"] = True

    result = evaluate_portal_readiness(review, evidence, history, attestation)

    check = next(item for item in result["checks"] if item["check"] == "revision_represented_if_occurred")
    assert check["passed"] is False
    assert result["ready_for_portal_reconsideration"] is False


def test_portal_gate_rejects_tampered_artifact_binding():
    review = _review()
    evidence = _evidence_review(review)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence)
    attestation = _completed_attestation(review, evidence, history)
    attestation["source_supplier_review_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source_supplier_review_sha256"):
        evaluate_portal_readiness(review, evidence, history, attestation)
