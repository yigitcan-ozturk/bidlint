from __future__ import annotations

import json

from bidlint.conformance import check_report_payload, main
from bidlint.errors import ExitCode
from bidlint.models import ComplianceReport, Finding, Requirement, SourceRef, Status, VendorFact


def _report_payload() -> dict:
    requirement = Requirement(
        id="R0001",
        text="Motor power shall be at least 10 kW",
        parameter="motor power",
        operator=">=",
        value=10.0,
        unit="kw",
        source=SourceRef(document="spec.pdf", page=1),
    )
    fact = VendorFact(
        parameter="motor power",
        raw_value="12 kW",
        value=12.0,
        unit="kw",
        source=SourceRef(document="vendor.pdf", page=2),
    )
    finding = Finding(
        requirement=requirement,
        vendor_fact=fact,
        status=Status.PASS,
        confidence=1.0,
        reason="offered value satisfies requirement",
    )
    return ComplianceReport(
        specification="spec.pdf",
        vendor="vendor.pdf",
        findings=[finding],
    ).to_dict()


def _codes(issues) -> set[str]:
    return {issue.code for issue in issues}


def test_generated_report_conforms_to_stable_contract():
    assert check_report_payload(_report_payload()) == ()


def test_additive_report_fields_are_allowed():
    payload = _report_payload()
    payload["future_minor_extension"] = {"safe": True}
    payload["findings"][0]["future_field"] = "allowed"
    assert check_report_payload(payload) == ()


def test_missing_required_key_is_rejected():
    payload = _report_payload()
    del payload["vendor"]
    issues = check_report_payload(payload)
    assert "missing_key" in _codes(issues)
    assert any(issue.path == "vendor" for issue in issues)


def test_counts_must_match_finding_statuses():
    payload = _report_payload()
    payload["counts"]["PASS"] = 0
    issues = check_report_payload(payload)
    assert "count_mismatch" in _codes(issues)


def test_score_must_follow_stable_semantics():
    payload = _report_payload()
    payload["compliance_score"] = 99.9
    issues = check_report_payload(payload)
    assert "score_mismatch" in _codes(issues)


def test_non_1x_report_is_rejected():
    payload = _report_payload()
    payload["version"] = "2.0.0"
    issues = check_report_payload(payload)
    assert "version" in _codes(issues)


def test_cli_validates_report_and_returns_success(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_payload()), encoding="utf-8")

    assert main([str(report), "--json"]) == ExitCode.SUCCESS
    output = json.loads(capsys.readouterr().out)
    assert output["conformant"] is True
    assert output["issue_count"] == 0


def test_cli_returns_input_exit_code_for_nonconformant_report(tmp_path, capsys):
    payload = _report_payload()
    payload["counts"]["PASS"] = 0
    report = tmp_path / "report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    assert main([str(report), "--json"]) == ExitCode.INPUT
    output = json.loads(capsys.readouterr().out)
    assert output["conformant"] is False
    assert output["issue_count"] >= 1


def test_cli_returns_input_exit_code_for_malformed_json(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text("{not-json", encoding="utf-8")

    assert main([str(report)]) == ExitCode.INPUT
    assert "contract validation failed" in capsys.readouterr().err


def test_cli_prints_manifest(capsys):
    assert main(["--manifest"]) == ExitCode.SUCCESS
    payload = json.loads(capsys.readouterr().out)
    assert payload["contract_version"] == "1"
    assert payload["scoring"]["review_in_denominator"] is False
