import json
from pathlib import Path

import pytest

from bidlint.supplier_evidence import evidence_assessment_template
from bidlint.supplier_evidence_binding import validate_evidence_assessment_with_files
from bidlint.supplier_files import build_supplier_evidence_file_manifest
from bidlint.supplier_history import initialize_history
from bidlint.supplier_pilot_attested_files import (
    evaluate_portal_readiness_with_files,
    pilot_attestation_template_with_files,
)
from bidlint.supplier_pilot_cli import main as pilot_main
from bidlint.supplier_response import ingest_supplier_response


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


def _review() -> dict:
    register = _register()
    response = _response()
    register_bytes = (json.dumps(register, sort_keys=True) + "\n").encode()
    response_bytes = (json.dumps(response, sort_keys=True) + "\n").encode()
    return ingest_supplier_response(
        register,
        response,
        register_bytes=register_bytes,
        response_bytes=response_bytes,
        register_name="register.json",
        response_name="response.json",
    )


def _manifest(tmp_path: Path, review: dict) -> dict:
    evidence = tmp_path / "MTC-317L.pdf"
    evidence.write_bytes(b"exact-certificate-bytes")
    return build_supplier_evidence_file_manifest(
        review,
        {
            "files": [
                {
                    "path": evidence.name,
                    "requirement_ids": ["R0001"],
                    "evidence_types": ["certificate"],
                    "note": "supplier returned MTC",
                }
            ]
        },
        evidence_map_dir=tmp_path,
    )


def _evidence_review(review: dict, manifest: dict) -> dict:
    assessment = evidence_assessment_template(review)
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
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    return validate_evidence_assessment_with_files(
        review,
        assessment,
        manifest,
        evidence_files_bytes=manifest_bytes,
        evidence_files_name="evidence-files.json",
    )


def _complete_attestation(attestation: dict) -> dict:
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


def test_file_backed_attestation_and_portal_gate_preserve_manifest_digest(tmp_path: Path):
    review = _review()
    manifest = _manifest(tmp_path, review)
    evidence_review = _evidence_review(review, manifest)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence_review)

    attestation = pilot_attestation_template_with_files(review, evidence_review, history, manifest)
    digest = attestation["source_supplier_evidence_files_sha256"]
    result = evaluate_portal_readiness_with_files(
        review,
        evidence_review,
        history,
        _complete_attestation(attestation),
        manifest,
    )

    assert len(digest) == 64
    assert result["ready_for_portal_reconsideration"] is True
    assert result["portal_decision"] == "RECONSIDER_SCOPE"
    assert result["automatic_portal_approval"] is False
    assert result["affects_evaluator"] is False
    assert result["provenance"]["supplier_evidence_files_sha256"] == digest
    assert any(
        check["check"] == "supplier_evidence_files_bound" and check["passed"] is True
        for check in result["checks"]
    )


def test_tampered_evidence_manifest_is_rejected_after_human_review(tmp_path: Path):
    review = _review()
    manifest = _manifest(tmp_path, review)
    evidence_review = _evidence_review(review, manifest)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence_review)
    tampered = json.loads(json.dumps(manifest))
    tampered["files"][0]["note"] = "changed after evidence review"

    with pytest.raises(ValueError, match="not bound to the supplied evidence-files manifest"):
        pilot_attestation_template_with_files(review, evidence_review, history, tampered)


def test_tampered_attestation_manifest_digest_is_rejected(tmp_path: Path):
    review = _review()
    manifest = _manifest(tmp_path, review)
    evidence_review = _evidence_review(review, manifest)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence_review)
    attestation = _complete_attestation(
        pilot_attestation_template_with_files(review, evidence_review, history, manifest)
    )
    attestation["source_supplier_evidence_files_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source_supplier_evidence_files_sha256"):
        evaluate_portal_readiness_with_files(review, evidence_review, history, attestation, manifest)


def test_cli_requires_manifest_for_file_backed_attestation(tmp_path: Path):
    review = _review()
    manifest = _manifest(tmp_path, review)
    evidence_review = _evidence_review(review, manifest)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence_review)

    review_path = tmp_path / "buyer-review.json"
    evidence_review_path = tmp_path / "evidence-review.json"
    history_path = tmp_path / "history.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    evidence_review_path.write_text(json.dumps(evidence_review), encoding="utf-8")
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(SystemExit, match="file-backed supplier evidence review requires --evidence-files"):
        pilot_main(
            [
                "attestation-template",
                str(review_path),
                str(evidence_review_path),
                str(history_path),
                str(tmp_path / "attestation.json"),
            ]
        )
