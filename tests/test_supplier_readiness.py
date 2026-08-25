import json
from pathlib import Path

import pytest

from bidlint.supplier_readiness import evaluate_supplier_response_readiness_files
from bidlint.supplier_readiness_cli import main


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
                "question": "Please confirm the offered material grade.",
                "finding_status": "REVIEW",
                "specification_source": None,
                "vendor_evidence": None,
            }
        ],
        "unanswered_requirements": [
            {
                "category": "UNANSWERED_REQUIREMENT",
                "status": "OPEN",
                "requirement_id": "R0002",
                "parameter": "ultrasonic test",
                "requirement_text": "UT evidence required",
                "question": "Please provide evidence for the ultrasonic test requirement.",
                "finding_status": "MISSING",
                "specification_source": None,
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
        "responder": {"name": "Frank", "company": "CSM"},
        "response_count": 2,
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
            },
            {
                "category": "UNANSWERED_REQUIREMENT",
                "requirement_id": "R0002",
                "parameter": "ultrasonic test",
                "finding_status": "MISSING",
                "supplier_response": "UT will be performed before shipment.",
                "offered_value": "",
                "offered_unit_or_designation": "",
                "evidence_reference": "",
                "supplier_comment": "Report will follow after testing.",
            },
        ],
    }


def _write_inputs(tmp_path: Path, response: dict | None = None) -> tuple[Path, Path]:
    register_path = tmp_path / "register.json"
    response_path = tmp_path / "response.json"
    register_path.write_text(json.dumps(_register()), encoding="utf-8")
    response_path.write_text(json.dumps(response or _response()), encoding="utf-8")
    return register_path, response_path


def test_readiness_passes_complete_response_without_requiring_every_evidence_reference(tmp_path: Path):
    register_path, response_path = _write_inputs(tmp_path)

    result = evaluate_supplier_response_readiness_files(register_path, response_path)

    assert result["ready_for_buyer_review"] is True
    assert result["automatic_acceptance"] is False
    assert result["human_review_required"] is True
    assert result["affects_evaluator"] is False
    assert result["counts"]["unanswered_items"] == 0
    assert result["counts"]["items_without_evidence_reference"] == 1
    evidence_check = next(
        item for item in result["checks"] if item["check"] == "evidence_reference_coverage_complete"
    )
    assert evidence_check["passed"] is False
    assert evidence_check["blocking"] is False


def test_readiness_blocks_missing_responder_identity(tmp_path: Path):
    response = _response()
    response["responder"]["name"] = ""
    register_path, response_path = _write_inputs(tmp_path, response)

    result = evaluate_supplier_response_readiness_files(register_path, response_path)

    assert result["ready_for_buyer_review"] is False
    assert "responder_name_present" in result["blocking_failures"]


def test_readiness_blocks_unanswered_open_item(tmp_path: Path):
    response = _response()
    response["responses"][1]["supplier_response"] = ""
    response["responses"][1]["offered_value"] = ""
    register_path, response_path = _write_inputs(tmp_path, response)

    result = evaluate_supplier_response_readiness_files(register_path, response_path)

    assert result["ready_for_buyer_review"] is False
    assert result["unanswered_requirement_ids"] == ["R0002"]
    assert "all_open_items_answered" in result["blocking_failures"]


def test_readiness_rejects_identity_mismatch_fail_closed(tmp_path: Path):
    response = _response()
    response["responses"][0]["parameter"] = "wrong parameter"
    register_path, response_path = _write_inputs(tmp_path, response)

    with pytest.raises(ValueError, match="parameter mismatch"):
        evaluate_supplier_response_readiness_files(register_path, response_path)


def test_cli_returns_two_and_writes_report_when_not_ready(tmp_path: Path):
    response = _response()
    response["responses"][0]["supplier_response"] = ""
    response["responses"][0]["offered_value"] = ""
    register_path, response_path = _write_inputs(tmp_path, response)
    output = tmp_path / "readiness.json"

    assert main([str(register_path), str(response_path), str(output)]) == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ready_for_buyer_review"] is False
    assert "R0001" in report["unanswered_requirement_ids"]


def test_cli_returns_zero_for_ready_response(tmp_path: Path):
    register_path, response_path = _write_inputs(tmp_path)
    output = tmp_path / "readiness.json"

    assert main([str(register_path), str(response_path), str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ready_for_buyer_review"] is True
