import hashlib
import json
from pathlib import Path

import pytest

from bidlint.supplier_response_cli import main


def _register() -> dict:
    return {
        "contract": "bidlint.procurement-clarifications",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.2.0.dev0",
        "specification": "317L-rfq.pdf",
        "vendor": "supplier-offer.xlsx",
        "counts": {"bidder_clarifications": 1, "unanswered_requirements": 1, "open_items": 2},
        "bidder_clarifications": [
            {
                "category": "BIDDER_CLARIFICATION",
                "status": "OPEN",
                "requirement_id": "R0001",
                "parameter": "material grade",
                "requirement_text": "Material shall be ASTM A182 F317L",
                "question": "Please clarify the offered material grade and provide traceable evidence.",
                "finding_status": "REVIEW",
                "confidence": 0.8,
                "evaluator_reason": "qualitative designation requires review",
                "specification_source": {
                    "document": "317L-rfq.pdf",
                    "page": 1,
                    "line": None,
                    "section": None,
                },
                "vendor_evidence": {
                    "parameter": "material",
                    "raw_value": "SS 317L",
                    "value": None,
                    "unit": None,
                    "source": {
                        "document": "supplier-offer.xlsx",
                        "page": None,
                        "line": None,
                        "section": "Offer",
                    },
                },
            }
        ],
        "unanswered_requirements": [
            {
                "category": "UNANSWERED_REQUIREMENT",
                "status": "OPEN",
                "requirement_id": "R0002",
                "parameter": "ultrasonic test",
                "requirement_text": "UT evidence required",
                "question": "Please provide technical evidence addressing requirement R0002 (ultrasonic test).",
                "finding_status": "MISSING",
                "confidence": 0.0,
                "evaluator_reason": "no matching vendor evidence found",
                "specification_source": {
                    "document": "317L-rfq.pdf",
                    "page": 1,
                    "line": None,
                    "section": None,
                },
                "vendor_evidence": None,
            }
        ],
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
        "responder": {"name": "Supplier Engineer", "company": "CSM Tech"},
        "response_count": 2,
        "responses": [
            {
                "category": "BIDDER_CLARIFICATION",
                "requirement_id": "R0001",
                "parameter": "material grade",
                "finding_status": "REVIEW",
                "supplier_response": "We confirm ASTM A182 F317L.",
                "offered_value": "F317L",
                "offered_unit_or_designation": "ASTM A182 F317L",
                "evidence_reference": "MTC to be supplied with shipment",
                "supplier_comment": "",
            },
            {
                "category": "UNANSWERED_REQUIREMENT",
                "requirement_id": "R0002",
                "parameter": "ultrasonic test",
                "finding_status": "MISSING",
                "supplier_response": "",
                "offered_value": "",
                "offered_unit_or_designation": "",
                "evidence_reference": "",
                "supplier_comment": "UT basis still under confirmation.",
            },
        ],
    }


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_supplier_review_cli_writes_pending_human_review_with_provenance(tmp_path: Path):
    register_path = tmp_path / "clarifications.json"
    response_path = tmp_path / "supplier-response.json"
    output_path = tmp_path / "buyer-review.json"
    register_bytes = (json.dumps(_register(), indent=2) + "\n").encode()
    response_bytes = (json.dumps(_response(), indent=2) + "\n").encode()
    register_path.write_bytes(register_bytes)
    response_path.write_bytes(response_bytes)

    assert main([str(register_path), str(response_path), str(output_path)]) == 0

    review = json.loads(output_path.read_text(encoding="utf-8"))
    assert review["contract"] == "bidlint.supplier-clarification-review"
    assert review["review_status"] == "PENDING_REVIEW"
    assert review["automatic_acceptance"] is False
    assert review["human_review_required"] is True
    assert review["counts"] == {
        "open_items": 2,
        "responses_present": 1,
        "evidence_references_present": 1,
    }
    assert review["items"][0]["review_status"] == "PENDING_REVIEW"
    assert review["items"][0]["supplier_response"] == "We confirm ASTM A182 F317L."
    assert review["provenance"]["clarification_register"]["byte_sha256"] == hashlib.sha256(register_bytes).hexdigest()
    assert review["provenance"]["supplier_response"]["byte_sha256"] == hashlib.sha256(response_bytes).hexdigest()
    assert review["provenance"]["source_register_binding"]["mechanism"] == "structural-metadata-and-item-identity"


def test_supplier_review_accepts_optional_declared_register_digest(tmp_path: Path):
    register = _register()
    response = _response()
    response["source_register_sha256"] = _canonical_sha256(register)
    register_path = tmp_path / "clarifications.json"
    response_path = tmp_path / "supplier-response.json"
    output_path = tmp_path / "buyer-review.json"
    register_path.write_text(json.dumps(register), encoding="utf-8")
    response_path.write_text(json.dumps(response), encoding="utf-8")

    assert main([str(register_path), str(response_path), str(output_path)]) == 0
    review = json.loads(output_path.read_text(encoding="utf-8"))
    binding = review["provenance"]["source_register_binding"]
    assert binding["mechanism"] == "declared-canonical-sha256"
    assert binding["response_declared_sha256"] == response["source_register_sha256"]


def test_supplier_review_rejects_wrong_declared_register_digest(tmp_path: Path):
    register_path = tmp_path / "clarifications.json"
    response_path = tmp_path / "supplier-response.json"
    output_path = tmp_path / "buyer-review.json"
    response = _response()
    response["source_register_sha256"] = "0" * 64
    register_path.write_text(json.dumps(_register()), encoding="utf-8")
    response_path.write_text(json.dumps(response), encoding="utf-8")

    with pytest.raises(SystemExit, match="source_register_sha256 does not match"):
        main([str(register_path), str(response_path), str(output_path)])


def test_supplier_review_rejects_missing_response_item(tmp_path: Path):
    register_path = tmp_path / "clarifications.json"
    response_path = tmp_path / "supplier-response.json"
    output_path = tmp_path / "buyer-review.json"
    response = _response()
    response["responses"] = response["responses"][:1]
    response["response_count"] = 1
    register_path.write_text(json.dumps(_register()), encoding="utf-8")
    response_path.write_text(json.dumps(response), encoding="utf-8")

    with pytest.raises(SystemExit, match=r"missing requirement_id\(s\): R0002"):
        main([str(register_path), str(response_path), str(output_path)])


def test_supplier_review_rejects_mutated_item_identity(tmp_path: Path):
    register_path = tmp_path / "clarifications.json"
    response_path = tmp_path / "supplier-response.json"
    output_path = tmp_path / "buyer-review.json"
    response = _response()
    response["responses"][0]["parameter"] = "different parameter"
    register_path.write_text(json.dumps(_register()), encoding="utf-8")
    response_path.write_text(json.dumps(response), encoding="utf-8")

    with pytest.raises(SystemExit, match="supplier response parameter mismatch for R0001"):
        main([str(register_path), str(response_path), str(output_path)])
