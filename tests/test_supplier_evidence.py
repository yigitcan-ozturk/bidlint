import json
from pathlib import Path

import pytest

from bidlint.supplier_evidence import evidence_assessment_template
from bidlint.supplier_evidence_cli import main


def _buyer_review() -> dict:
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
        "responder": {"name": "Supplier Engineer", "company": "CSM Tech"},
        "counts": {
            "open_items": 2,
            "responses_present": 2,
            "evidence_references_present": 2,
        },
        "provenance": {},
        "items": [
            {
                "requirement_id": "R0001",
                "category": "BIDDER_CLARIFICATION",
                "parameter": "material grade",
                "requirement_text": "Material shall be ASTM A182 F317L",
                "question": "Confirm material grade.",
                "prior_finding_status": "REVIEW",
                "specification_source": {"document": "317L-rfq.pdf", "page": 1},
                "prior_vendor_evidence": None,
                "supplier_response": "Confirmed F317L.",
                "offered_value": "F317L",
                "offered_unit_or_designation": "ASTM A182 F317L",
                "evidence_reference": "MTC",
                "supplier_comment": "",
                "response_present": True,
                "evidence_reference_present": True,
                "review_status": "PENDING_REVIEW",
                "human_review_required": True,
            },
            {
                "requirement_id": "R0002",
                "category": "UNANSWERED_REQUIREMENT",
                "parameter": "ultrasonic test",
                "requirement_text": "UT evidence required",
                "question": "Provide UT evidence.",
                "prior_finding_status": "MISSING",
                "specification_source": {"document": "317L-rfq.pdf", "page": 1},
                "prior_vendor_evidence": None,
                "supplier_response": "UT will be performed.",
                "offered_value": "",
                "offered_unit_or_designation": "",
                "evidence_reference": "UT procedure CSM-UT-12",
                "supplier_comment": "",
                "response_present": True,
                "evidence_reference_present": True,
                "review_status": "PENDING_REVIEW",
                "human_review_required": True,
            },
        ],
    }


def _completed_assessment() -> dict:
    assessment = evidence_assessment_template(_buyer_review())
    assessment["reviewer"] = {
        "name": "Buyer Engineer",
        "role": "Technical Reviewer",
        "organization": "Pamilanga",
    }
    for item in assessment["items"]:
        for kind, entry in item["evidence"].items():
            if kind == "calculation":
                entry["required"] = "NOT_REQUIRED"
                entry["status"] = "NOT_REQUIRED"
            else:
                entry["required"] = "REQUIRED"
                entry["status"] = "ADEQUATE"
                entry["references"] = [f"{item['requirement_id']}-{kind}-ref"]
        item["overall"] = "ADEQUATE"
        item["rationale"] = "Required evidence references are present for technical review."
    return assessment


def test_evidence_template_has_explicit_adequacy_dimensions(tmp_path: Path):
    review_path = tmp_path / "buyer-review.json"
    output_path = tmp_path / "assessment.json"
    review_path.write_text(json.dumps(_buyer_review()), encoding="utf-8")

    assert main(["template", str(review_path), str(output_path)]) == 0

    assessment = json.loads(output_path.read_text(encoding="utf-8"))
    assert assessment["contract"] == "bidlint.supplier-evidence-assessment"
    assert set(assessment["items"][0]["evidence"]) == {
        "calculation",
        "certificate",
        "test_basis",
        "supporting_document",
    }
    assert assessment["items"][0]["evidence"]["certificate"]["required"] == "UNKNOWN"
    assert assessment["items"][0]["overall"] == "NOT_ASSESSED"


def test_evidence_validate_writes_human_only_review(tmp_path: Path):
    review_path = tmp_path / "buyer-review.json"
    assessment_path = tmp_path / "assessment.json"
    output_path = tmp_path / "evidence-review.json"
    review_path.write_text(json.dumps(_buyer_review(), indent=2) + "\n", encoding="utf-8")
    assessment_path.write_text(json.dumps(_completed_assessment(), indent=2) + "\n", encoding="utf-8")

    assert main(["validate", str(review_path), str(assessment_path), str(output_path)]) == 0

    validated = json.loads(output_path.read_text(encoding="utf-8"))
    assert validated["contract"] == "bidlint.supplier-evidence-review"
    assert validated["human_review_only"] is True
    assert validated["affects_evaluator"] is False
    assert validated["counts"]["ADEQUATE"] == 2
    assert validated["items"][0]["evidence"]["certificate"]["status"] == "ADEQUATE"
    assert validated["provenance"]["supplier_clarification_review"]["byte_sha256"]
    assert validated["provenance"]["supplier_evidence_assessment"]["byte_sha256"]


def test_evidence_validate_rejects_source_digest_mismatch(tmp_path: Path):
    review_path = tmp_path / "buyer-review.json"
    assessment_path = tmp_path / "assessment.json"
    output_path = tmp_path / "evidence-review.json"
    review_path.write_text(json.dumps(_buyer_review()), encoding="utf-8")
    assessment = _completed_assessment()
    assessment["source_supplier_review_sha256"] = "0" * 64
    assessment_path.write_text(json.dumps(assessment), encoding="utf-8")

    with pytest.raises(SystemExit, match="source_supplier_review_sha256 does not match"):
        main(["validate", str(review_path), str(assessment_path), str(output_path)])


def test_evidence_validate_rejects_adequate_without_reference(tmp_path: Path):
    review_path = tmp_path / "buyer-review.json"
    assessment_path = tmp_path / "assessment.json"
    output_path = tmp_path / "evidence-review.json"
    review_path.write_text(json.dumps(_buyer_review()), encoding="utf-8")
    assessment = _completed_assessment()
    assessment["items"][0]["evidence"]["certificate"]["references"] = []
    assessment_path.write_text(json.dumps(assessment), encoding="utf-8")

    with pytest.raises(SystemExit, match="R0001/certificate ADEQUATE status requires at least one evidence reference"):
        main(["validate", str(review_path), str(assessment_path), str(output_path)])


def test_evidence_validate_rejects_overall_adequate_with_missing_required_evidence(tmp_path: Path):
    review_path = tmp_path / "buyer-review.json"
    assessment_path = tmp_path / "assessment.json"
    output_path = tmp_path / "evidence-review.json"
    review_path.write_text(json.dumps(_buyer_review()), encoding="utf-8")
    assessment = _completed_assessment()
    assessment["items"][1]["evidence"]["test_basis"]["status"] = "MISSING"
    assessment["items"][1]["evidence"]["test_basis"]["references"] = []
    assessment_path.write_text(json.dumps(assessment), encoding="utf-8")

    with pytest.raises(SystemExit, match="R0002 cannot be ADEQUATE while required evidence is not ADEQUATE"):
        main(["validate", str(review_path), str(assessment_path), str(output_path)])
