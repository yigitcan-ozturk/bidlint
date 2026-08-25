import hashlib
import json
from pathlib import Path

import pytest

from bidlint.supplier_intake_cli import main


def _register() -> dict:
    return {
        "contract": "bidlint.procurement-clarifications",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.1.0",
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
                "specification_source": {"document": "317L-rfq.pdf", "page": 1, "line": None, "section": None},
                "vendor_evidence": {
                    "parameter": "material",
                    "raw_value": "SS 317L",
                    "value": None,
                    "unit": None,
                    "source": {"document": "supplier-offer.xlsx", "page": None, "line": None, "section": "Offer"},
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
                "specification_source": {"document": "317L-rfq.pdf", "page": 1, "line": None, "section": None},
                "vendor_evidence": None,
            }
        ],
    }


def test_supplier_intake_cli_writes_offline_html(tmp_path: Path):
    source = tmp_path / "clarifications.json"
    output = tmp_path / "supplier-intake.html"
    register = _register()
    source.write_text(json.dumps(register), encoding="utf-8")

    assert main([str(source), str(output)]) == 0

    rendered = output.read_text(encoding="utf-8")
    canonical = json.dumps(register, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_digest = hashlib.sha256(canonical).hexdigest()
    assert "BidLint Supplier Clarification" in rendered
    assert "R0001" in rendered
    assert "R0002" in rendered
    assert "Download response JSON" in rendered
    assert "bidlint.supplier-clarification-response" in rendered
    assert f'"source_register_sha256":"{expected_digest}"' in rendered
    assert "fetch(" not in rendered
    assert "XMLHttpRequest" not in rendered


def test_supplier_intake_rejects_wrong_contract(tmp_path: Path):
    source = tmp_path / "clarifications.json"
    output = tmp_path / "supplier-intake.html"
    payload = _register()
    payload["contract"] = "wrong.contract"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit, match="requires bidlint.procurement-clarifications input"):
        main([str(source), str(output)])


def test_supplier_intake_requires_html_output(tmp_path: Path):
    source = tmp_path / "clarifications.json"
    source.write_text(json.dumps(_register()), encoding="utf-8")

    with pytest.raises(SystemExit, match="output must end in .html"):
        main([str(source), str(tmp_path / "supplier-intake.txt")])
