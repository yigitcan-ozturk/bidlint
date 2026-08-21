import pytest

from bidlint.clarifications import clarification_portfolio, clarification_register
from bidlint.deviations import procurement_review_register
from bidlint.models import (
    ComplianceReport,
    Finding,
    KnockoutAssessment,
    KnockoutCriterion,
    KnockoutStatus,
    Requirement,
    SourceRef,
    Status,
    VendorFact,
)
from bidlint.procurement import procurement_portfolio, procurement_readiness
from bidlint.scorecard import supplier_scorecard_signal_v2


def _finding(requirement_id: str, status: Status, *, fact: bool = True) -> Finding:
    requirement = Requirement(
        id=requirement_id,
        text=f"Requirement {requirement_id}",
        parameter=f"parameter {requirement_id}",
        source=SourceRef("spec.pdf", page=1),
    )
    vendor_fact = (
        VendorFact(
            parameter=requirement.parameter,
            raw_value="offered",
            source=SourceRef("vendor.pdf", page=2),
        )
        if fact
        else None
    )
    return Finding(
        requirement=requirement,
        vendor_fact=vendor_fact,
        status=status,
        confidence=0.8,
        reason=f"reason {requirement_id}",
    )


def _knockout(status: KnockoutStatus, criteria: list[tuple[str, Status]]) -> KnockoutAssessment:
    return KnockoutAssessment(
        status=status,
        criteria=[
            KnockoutCriterion(
                requirement_id=requirement_id,
                parameter=requirement_id,
                finding_status=finding_status,
                reason="knockout audit",
            )
            for requirement_id, finding_status in criteria
        ],
    )


def _report(
    vendor: str,
    statuses: list[Status],
    knockout: KnockoutAssessment | None = None,
) -> ComplianceReport:
    findings = [
        _finding(f"R{index:04d}", status, fact=status != Status.MISSING)
        for index, status in enumerate(statuses, start=1)
    ]
    return ComplianceReport("spec.pdf", vendor, findings, knockout)


def test_clarification_register_splits_review_and_missing_with_provenance():
    payload = clarification_register(
        _report("Supplier A", [Status.PASS, Status.REVIEW, Status.MISSING, Status.DEVIATION])
    )

    assert payload["counts"] == {
        "bidder_clarifications": 1,
        "unanswered_requirements": 1,
        "open_items": 2,
    }
    assert payload["bidder_clarifications"][0]["requirement_id"] == "R0002"
    assert payload["unanswered_requirements"][0]["requirement_id"] == "R0003"
    assert payload["bidder_clarifications"][0]["specification_source"]["page"] == 1
    assert payload["bidder_clarifications"][0]["vendor_evidence"]["source"]["page"] == 2
    assert payload["unanswered_requirements"][0]["vendor_evidence"] is None


def test_clarification_register_rejects_duplicate_requirement_ids():
    report = _report("Supplier A", [Status.REVIEW])
    report.findings.append(_finding("R0001", Status.MISSING, fact=False))

    with pytest.raises(ValueError, match="duplicate requirement"):
        clarification_register(report)


def test_clarification_portfolio_preserves_vendor_input_order():
    payload = clarification_portfolio(
        [
            _report("Supplier B", [Status.MISSING]),
            _report("Supplier A", [Status.REVIEW]),
        ]
    )
    assert [register["vendor"] for register in payload["registers"]] == ["Supplier B", "Supplier A"]


def test_review_register_separates_deviation_and_internal_review():
    payload = procurement_review_register(
        _report("Supplier A", [Status.DEVIATION, Status.REVIEW, Status.MISSING])
    )

    assert [item["requirement_id"] for item in payload["deviations"]] == ["R0001"]
    assert [item["requirement_id"] for item in payload["review_queue"]] == ["R0002"]
    assert payload["counts"]["open_items"] == 2


def test_review_register_marks_knockout_context_without_changing_finding():
    knockout = _knockout(
        KnockoutStatus.DISQUALIFIED,
        [("R0001", Status.DEVIATION)],
    )
    payload = procurement_review_register(
        _report("Supplier A", [Status.DEVIATION], knockout)
    )

    assert payload["deviations"][0]["knockout_criterion"] is True
    assert payload["deviations"][0]["finding_status"] == "DEVIATION"


def test_procurement_requires_explicit_knockout_policy():
    payload = procurement_readiness(_report("Supplier A", [Status.PASS]))
    assert payload["status"] == "POLICY_REQUIRED"


def test_procurement_disqualification_has_priority():
    knockout = _knockout(
        KnockoutStatus.DISQUALIFIED,
        [("R0001", Status.DEVIATION)],
    )
    payload = procurement_readiness(
        _report("Supplier A", [Status.DEVIATION, Status.REVIEW], knockout)
    )
    assert payload["status"] == "DISQUALIFIED"


def test_procurement_knockout_review_is_not_auto_accepted():
    knockout = _knockout(
        KnockoutStatus.REVIEW_REQUIRED,
        [("R0001", Status.REVIEW)],
    )
    payload = procurement_readiness(
        _report("Supplier A", [Status.REVIEW], knockout)
    )
    assert payload["status"] == "REVIEW_REQUIRED"


def test_procurement_open_deviation_requires_action():
    knockout = _knockout(
        KnockoutStatus.ELIGIBLE,
        [("R0001", Status.PASS)],
    )
    payload = procurement_readiness(
        _report("Supplier A", [Status.PASS, Status.DEVIATION], knockout)
    )
    assert payload["status"] == "ACTION_REQUIRED"


def test_procurement_clean_eligible_report_is_ready():
    knockout = _knockout(
        KnockoutStatus.ELIGIBLE,
        [("R0001", Status.PASS)],
    )
    payload = procurement_readiness(
        _report("Supplier A", [Status.PASS, Status.PASS], knockout)
    )
    assert payload["status"] == "READY"


def test_procurement_portfolio_ranks_only_ready_suppliers():
    eligible = _knockout(
        KnockoutStatus.ELIGIBLE,
        [("R0001", Status.PASS)],
    )
    disqualified = _knockout(
        KnockoutStatus.DISQUALIFIED,
        [("R0001", Status.DEVIATION)],
    )
    payload = procurement_portfolio(
        [
            _report("Supplier B", [Status.DEVIATION], disqualified),
            _report("Supplier A", [Status.PASS], eligible),
        ]
    )

    assert [item["vendor"] for item in payload["ready_ranking"]] == ["Supplier A"]
    assert [item["vendor"] for item in payload["excluded"]] == ["Supplier B"]
    assert "rank" not in payload["excluded"][0]


def test_scorecard_v2_emits_numeric_signal_only_for_ready_supplier():
    eligible = _knockout(
        KnockoutStatus.ELIGIBLE,
        [("R0001", Status.PASS)],
    )
    ready = supplier_scorecard_signal_v2(
        _report("Supplier A", [Status.PASS], eligible),
        "Supplier A",
    )
    blocked = supplier_scorecard_signal_v2(
        _report("Supplier B", [Status.PASS]),
        "Supplier B",
    )

    assert ready["contract_version"] == "2"
    assert ready["technical_compliance_status"] == "READY"
    assert ready["technical_compliance"] == 100.0
    assert blocked["technical_compliance_status"] == "POLICY_REQUIRED"
    assert blocked["technical_compliance"] is None
    assert blocked["technical_compliance_audit"]["compliance_score"] == 100.0
