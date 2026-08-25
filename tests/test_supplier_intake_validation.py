from bidlint.supplier_intake_validated import validated_supplier_intake_html_from_register


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
                "specification_source": None,
                "vendor_evidence": None,
            }
        ],
        "unanswered_requirements": [],
    }


def test_validated_form_adds_local_readiness_check_before_download():
    rendered = validated_supplier_intake_html_from_register(_register())

    assert "Check response" in rendered
    assert "function validateResponse(payload)" in rendered
    assert "Responder name is required." in rendered
    assert "Responder company is required." in rendered
    assert "technical response or offered value is required." in rendered
    assert "if (errors.length)" in rendered
    assert "return;" in rendered
    assert "Response is complete enough to download." in rendered


def test_validated_form_remains_self_contained_and_offline():
    rendered = validated_supplier_intake_html_from_register(_register())

    assert "fetch(" not in rendered
    assert "XMLHttpRequest" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered
    assert "Download response JSON" in rendered


def test_validated_form_does_not_make_evidence_reference_a_download_blocker():
    rendered = validated_supplier_intake_html_from_register(_register())

    validator_start = rendered.index("function validateResponse(payload)")
    validator_end = rendered.index("function showReadiness(errors)")
    validator = rendered[validator_start:validator_end]
    assert "evidence_reference" not in validator
