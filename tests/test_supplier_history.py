import copy
import hashlib
import json

import pytest

from bidlint.supplier_history import append_history, initialize_history, validate_history


def _review(value: str = "F317L", evidence: str = "MTC rev A") -> dict:
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
        "counts": {"open_items": 1, "responses_present": 1, "evidence_references_present": 1},
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
                "supplier_response": f"Confirmed {value}.",
                "offered_value": value,
                "offered_unit_or_designation": f"ASTM A182 {value}",
                "evidence_reference": evidence,
                "supplier_comment": "",
                "response_present": True,
                "evidence_reference_present": True,
                "review_status": "PENDING_REVIEW",
                "human_review_required": True,
            }
        ],
    }


def _evidence_review(review: dict) -> dict:
    payload = json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "contract": "bidlint.supplier-evidence-review",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.2.0.dev0",
        "specification": review["specification"],
        "vendor": review["vendor"],
        "human_review_only": True,
        "affects_evaluator": False,
        "reviewer": {"name": "Buyer", "role": "Engineer", "organization": "Pamilanga"},
        "counts": {"ADEQUATE": 1},
        "provenance": {"supplier_clarification_review": {"canonical_sha256": digest}},
        "items": [
            {
                "requirement_id": "R0001",
                "parameter": "material grade",
                "prior_finding_status": "REVIEW",
                "evidence": {
                    "calculation": {
                        "required": "NOT_REQUIRED",
                        "status": "NOT_REQUIRED",
                        "references": [],
                        "note": "",
                    },
                    "certificate": {
                        "required": "REQUIRED",
                        "status": "ADEQUATE",
                        "references": ["MTC"],
                        "note": "",
                    },
                    "test_basis": {
                        "required": "NOT_REQUIRED",
                        "status": "NOT_REQUIRED",
                        "references": [],
                        "note": "",
                    },
                    "supporting_document": {
                        "required": "NOT_REQUIRED",
                        "status": "NOT_REQUIRED",
                        "references": [],
                        "note": "",
                    },
                },
                "overall": "ADEQUATE",
                "rationale": "MTC reviewed",
            }
        ],
    }


def test_initialize_history_creates_hash_chained_immutable_revision():
    review = _review()
    evidence = _evidence_review(review)
    history = initialize_history(review, revision_id="R1", evidence_review=evidence)

    assert history["contract"] == "bidlint.supplier-clarification-history"
    assert history["active_revision_id"] == "R1"
    assert history["revision_count"] == 1
    assert history["human_review_only"] is True
    assert history["affects_evaluator"] is False
    assert history["revisions"][0]["parent_revision_sha256"] is None
    assert history["revisions"][0]["revision_sha256"] == history["active_revision_sha256"]
    assert validate_history(history)["valid"] is True


def test_append_unchanged_revision_keeps_no_conflict():
    history = initialize_history(_review(), revision_id="R1")
    updated = append_history(history, _review(), revision_id="R2", supersedes_revision_id="R1")

    assert updated["revision_count"] == 2
    assert updated["active_revision_id"] == "R2"
    assert updated["unresolved_conflict_count"] == 0
    assert updated["revisions"][-1]["changes_from_previous"][0]["change"] == "UNCHANGED"
    assert updated["revisions"][-1]["parent_revision_sha256"] == history["active_revision_sha256"]


def test_append_conflicting_offered_value_surfaces_pending_review():
    history = initialize_history(_review("F317L"), revision_id="R1")
    updated = append_history(
        history,
        _review("F316L", "MTC rev B"),
        revision_id="R2",
        supersedes_revision_id="R1",
    )

    assert updated["unresolved_conflict_count"] == 1
    assert updated["revisions"][-1]["changes_from_previous"][0]["change"] == "CONFLICT"
    conflict = updated["conflicts"][0]
    assert conflict["requirement_id"] == "R0001"
    assert set(conflict["fields"]) == {"offered_value", "offered_unit_or_designation"}
    assert conflict["resolution_status"] == "PENDING_REVIEW"


def test_append_rejects_branching_from_non_active_revision():
    history = initialize_history(_review(), revision_id="R1")
    history = append_history(history, _review(), revision_id="R2", supersedes_revision_id="R1")

    with pytest.raises(ValueError, match="must match the active revision"):
        append_history(history, _review(), revision_id="R3", supersedes_revision_id="R1")


def test_append_rejects_duplicate_revision_id():
    history = initialize_history(_review(), revision_id="R1")

    with pytest.raises(ValueError, match="revision_id already exists"):
        append_history(history, _review(), revision_id="R1", supersedes_revision_id="R1")


def test_evidence_review_must_bind_to_same_supplier_review():
    review = _review()
    evidence = _evidence_review(review)
    mutated = _review("F316L")

    with pytest.raises(ValueError, match="is not bound"):
        initialize_history(mutated, revision_id="R1", evidence_review=evidence)


def test_tampered_revision_digest_is_rejected():
    history = initialize_history(_review(), revision_id="R1")
    tampered = copy.deepcopy(history)
    tampered["revisions"][0]["items"][0]["offered_value"] = "F316L"

    with pytest.raises(ValueError, match="revision_sha256 mismatch"):
        validate_history(tampered)
