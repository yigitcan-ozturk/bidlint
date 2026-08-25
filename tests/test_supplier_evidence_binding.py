import json
from pathlib import Path

import pytest

from bidlint.supplier_evidence import evidence_assessment_template
from bidlint.supplier_evidence_binding import validate_evidence_assessment_with_files
from bidlint.supplier_evidence_cli import main as evidence_main
from bidlint.supplier_files import build_supplier_evidence_file_manifest
from bidlint.supplier_pilot_files import prepare_pilot_return_with_evidence_files


def _review(two_items: bool = False) -> dict:
    items = [
        {
            "requirement_id": "R0001",
            "parameter": "material grade",
            "prior_finding_status": "REVIEW",
        }
    ]
    if two_items:
        items.append(
            {
                "requirement_id": "R0002",
                "parameter": "ultrasonic test",
                "prior_finding_status": "MISSING",
            }
        )
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
        "items": items,
    }


def _assessment(review: dict, reference: str) -> dict:
    assessment = evidence_assessment_template(review)
    assessment["reviewer"] = {
        "name": "Buyer Engineer",
        "role": "Technical Reviewer",
        "organization": "Buyer",
    }
    for item in assessment["items"]:
        for kind, entry in item["evidence"].items():
            if item["requirement_id"] == "R0001" and kind == "certificate":
                entry["required"] = "REQUIRED"
                entry["status"] = "ADEQUATE"
                entry["references"] = [reference]
            else:
                entry["required"] = "NOT_REQUIRED"
                entry["status"] = "NOT_REQUIRED"
        item["overall"] = "ADEQUATE"
        item["rationale"] = "Reviewed by buyer."
    return assessment


def _file_manifest(tmp_path: Path, review: dict, *, requirement_id: str = "R0001") -> dict:
    evidence = tmp_path / "MTC-317L.pdf"
    evidence.write_bytes(b"exact-certificate-bytes")
    return build_supplier_evidence_file_manifest(
        review,
        {
            "files": [
                {
                    "path": evidence.name,
                    "requirement_ids": [requirement_id],
                    "evidence_types": ["certificate"],
                    "note": "supplier returned MTC",
                }
            ]
        },
        evidence_map_dir=tmp_path,
    )


def test_validated_evidence_review_cryptographically_binds_file_manifest(tmp_path: Path):
    review = _review()
    assessment = _assessment(review, "file:F001")
    manifest = _file_manifest(tmp_path, review)
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()

    validated = validate_evidence_assessment_with_files(
        review,
        assessment,
        manifest,
        evidence_files_bytes=manifest_bytes,
        evidence_files_name="evidence-files.json",
    )

    assert validated["human_review_only"] is True
    assert validated["affects_evaluator"] is False
    assert validated["evidence_file_reference_validation"]["validated"] is True
    assert validated["evidence_file_reference_validation"]["referenced_files"] == ["file:F001"]
    assert validated["provenance"]["supplier_evidence_files"]["name"] == "evidence-files.json"
    assert validated["provenance"]["supplier_evidence_files"]["byte_length"] == len(manifest_bytes)


def test_file_reference_without_manifest_fails_closed(tmp_path: Path):
    review = _review()
    assessment = _assessment(review, "file:F001")
    review_path = tmp_path / "buyer-review.json"
    assessment_path = tmp_path / "assessment.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    assessment_path.write_text(json.dumps(assessment), encoding="utf-8")

    with pytest.raises(SystemExit, match="file: evidence references require --evidence-files"):
        evidence_main(["validate", str(review_path), str(assessment_path), str(tmp_path / "out.json")])


def test_file_reference_must_match_requirement_binding(tmp_path: Path):
    review = _review(two_items=True)
    assessment = _assessment(review, "file:F001")
    manifest = _file_manifest(tmp_path, review, requirement_id="R0002")

    with pytest.raises(ValueError, match="not bound to requirement R0001"):
        validate_evidence_assessment_with_files(review, assessment, manifest)


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
                "evidence_reference": "MTC-317L.pdf",
                "supplier_comment": "",
            }
        ],
    }


def test_prepare_return_can_package_evidence_file_manifest(tmp_path: Path):
    register_path = tmp_path / "register.json"
    response_path = tmp_path / "response.json"
    evidence_path = tmp_path / "MTC-317L.pdf"
    evidence_map_path = tmp_path / "evidence-map.json"
    output = tmp_path / "pilot-return"
    register_path.write_text(json.dumps(_register()), encoding="utf-8")
    response_path.write_text(json.dumps(_response()), encoding="utf-8")
    evidence_path.write_bytes(b"certificate")
    evidence_map_path.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": evidence_path.name,
                        "requirement_ids": ["R0001"],
                        "evidence_types": ["certificate"],
                        "note": "returned with response",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = prepare_pilot_return_with_evidence_files(
        register_path,
        response_path,
        output,
        evidence_map_path=evidence_map_path,
    )

    assert (output / "evidence-files.json").exists()
    assert manifest["artifacts"]["evidence_files"]["file_count"] == 1
    assert "--evidence-files evidence-files.json" in manifest["next_action"]
