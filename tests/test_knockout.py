import json

import pytest

from bidlint.knockout import (
    apply_knockouts,
    load_knockout_file,
    validate_knockout_requirement_ids,
)
from bidlint.models import (
    ComplianceReport,
    Finding,
    KnockoutStatus,
    Requirement,
    Status,
)
from bidlint.portfolio import rank_reports
from bidlint.report import portfolio_to_json, to_json
from bidlint.scorecard import supplier_scorecard_signal


def finding(identifier: str, status: Status, *, mandatory: bool = True) -> Finding:
    requirement = Requirement(
        id=identifier,
        text=f"Requirement {identifier}",
        parameter=f"parameter {identifier}",
        mandatory=mandatory,
    )
    return Finding(
        requirement=requirement,
        vendor_fact=None,
        status=status,
        confidence=1.0,
        reason=f"{identifier} is {status.value}",
    )


def report(vendor: str, statuses: list[Status]) -> ComplianceReport:
    return ComplianceReport(
        specification="spec.pdf",
        vendor=vendor,
        findings=[finding(f"R{index:04d}", status) for index, status in enumerate(statuses, start=1)],
    )


def test_policy_loader_is_strict(tmp_path):
    policy = tmp_path / "knockouts.json"
    policy.write_text(json.dumps({"requirement_ids": [" R0002 ", "R0001"]}), encoding="utf-8")
    assert load_knockout_file(policy) == ("R0002", "R0001")

    policy.write_text(json.dumps({"requirement_ids": ["R0001"], "mode": "auto"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown knockout policy key"):
        load_knockout_file(policy)

    policy.write_text(json.dumps({"requirement_ids": ["R0001", "R0001"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate knockout requirement id"):
        load_knockout_file(policy)

    policy.write_text(json.dumps({"requirement_ids": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="must not be empty"):
        load_knockout_file(policy)


def test_policy_ids_must_exist_in_specification():
    requirements = [finding("R0001", Status.PASS).requirement]
    with pytest.raises(ValueError, match="unknown knockout requirement id"):
        validate_knockout_requirement_ids(requirements, ["R9999"])


def test_all_selected_pass_is_eligible():
    value = report("eligible.pdf", [Status.PASS, Status.PASS])
    assessment = apply_knockouts(value, ["R0002", "R0001"])

    assert assessment.status == KnockoutStatus.ELIGIBLE
    assert assessment.requirement_ids == ["R0002", "R0001"]
    assert assessment.failed_requirement_ids == []
    assert assessment.review_requirement_ids == []


def test_review_requires_review_without_disqualifying():
    value = report("review.pdf", [Status.PASS, Status.REVIEW])
    assessment = apply_knockouts(value, ["R0001", "R0002"])

    assert assessment.status == KnockoutStatus.REVIEW_REQUIRED
    assert assessment.review_requirement_ids == ["R0002"]


def test_failure_disqualifies_and_takes_precedence_over_review():
    value = report("failed.pdf", [Status.REVIEW, Status.MISSING, Status.DEVIATION])
    assessment = apply_knockouts(value, ["R0001", "R0002", "R0003"])

    assert assessment.status == KnockoutStatus.DISQUALIFIED
    assert assessment.failed_requirement_ids == ["R0002", "R0003"]
    assert assessment.review_requirement_ids == ["R0001"]


def test_mandatory_flag_does_not_implicitly_create_knockout():
    value = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor.pdf",
        findings=[finding("R0001", Status.DEVIATION, mandatory=True)],
    )
    assert value.knockout is None
    assert "knockout" not in value.to_dict()


def test_gate_aware_ranking_precedes_compliance_score():
    eligible = report("eligible.pdf", [Status.PASS, Status.DEVIATION])
    review = report("review.pdf", [Status.REVIEW, Status.PASS])
    failed = report("failed.pdf", [Status.DEVIATION, Status.PASS])

    apply_knockouts(eligible, ["R0001"])
    apply_knockouts(review, ["R0001"])
    apply_knockouts(failed, ["R0001"])

    assert [item.vendor for item in rank_reports([failed, review, eligible])] == [
        "eligible.pdf",
        "review.pdf",
        "failed.pdf",
    ]


def test_mixed_assessed_and_unassessed_ranking_is_rejected():
    assessed = report("assessed.pdf", [Status.PASS])
    unassessed = report("unassessed.pdf", [Status.PASS])
    apply_knockouts(assessed, ["R0001"])

    with pytest.raises(ValueError, match="assessed and unassessed"):
        rank_reports([assessed, unassessed])


def test_single_report_json_is_additive_only_when_active():
    value = report("vendor.pdf", [Status.PASS])
    plain = json.loads(to_json(value))
    assert "knockout" not in plain

    apply_knockouts(value, ["R0001"])
    assessed = json.loads(to_json(value))
    assert assessed["knockout"]["status"] == "ELIGIBLE"
    assert assessed["knockout"]["requirement_ids"] == ["R0001"]


def test_portfolio_json_is_gate_aware_but_default_shape_is_preserved():
    a = report("a.pdf", [Status.PASS])
    b = report("b.pdf", [Status.DEVIATION])
    plain = json.loads(portfolio_to_json([b, a]))
    assert "knockout_status" not in plain["ranking"][0]

    apply_knockouts(a, ["R0001"])
    apply_knockouts(b, ["R0001"])
    assessed = json.loads(portfolio_to_json([b, a]))
    assert [item["vendor"] for item in assessed["ranking"]] == ["a.pdf", "b.pdf"]
    assert [item["knockout_status"] for item in assessed["ranking"]] == ["ELIGIBLE", "DISQUALIFIED"]


def test_scorecard_v1_rejects_knockout_assessed_report():
    value = report("vendor.pdf", [Status.PASS])
    apply_knockouts(value, ["R0001"])

    with pytest.raises(ValueError, match="contract v1"):
        supplier_scorecard_signal(value, "Supplier A")
