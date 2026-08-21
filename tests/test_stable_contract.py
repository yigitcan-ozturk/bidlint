from __future__ import annotations

import argparse

from bidlint.cli import build_parser
from bidlint.contracts import (
    CLI_EXIT_CODES,
    CLI_REQUIRED_COMMANDS,
    FINDING_REQUIRED_FIELDS,
    KNOCKOUT_STATUS_VALUES,
    REPORT_REQUIRED_KEYS,
    STATUS_VALUES,
    VENDOR_FACT_REQUIRED_FIELDS,
    stable_contract_manifest,
    validate_runtime_contract,
)
from bidlint.errors import ExitCode
from bidlint.models import ComplianceReport, Finding, Requirement, SourceRef, Status, VendorFact


def _requirement(identifier: str) -> Requirement:
    return Requirement(
        id=identifier,
        text=f"Requirement {identifier}",
        parameter=f"parameter {identifier}",
        operator=">=",
        value=10.0,
        unit="kw",
        source=SourceRef(document="spec.pdf", page=1),
    )


def _finding(identifier: str, status: Status) -> Finding:
    fact = None
    if status is not Status.MISSING:
        fact = VendorFact(
            parameter=f"parameter {identifier}",
            raw_value="10 kW",
            value=10.0,
            unit="kw",
            source=SourceRef(document="vendor.pdf", page=1),
        )
    return Finding(
        requirement=_requirement(identifier),
        vendor_fact=fact,
        status=status,
        confidence=1.0,
        reason=f"{status.value} fixture",
    )


def test_runtime_satisfies_stable_contract_manifest():
    validate_runtime_contract()
    manifest = stable_contract_manifest()
    assert manifest["contract_version"] == "1"
    assert manifest["statuses"] == list(STATUS_VALUES)
    assert manifest["knockout_statuses"] == list(KNOCKOUT_STATUS_VALUES)


def test_public_cli_commands_remain_available():
    parser = build_parser()
    subparsers = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
    assert len(subparsers) == 1
    choices = set(subparsers[0].choices)
    assert set(CLI_REQUIRED_COMMANDS).issubset(choices)


def test_public_exit_codes_are_frozen():
    assert {member.name: int(member) for member in ExitCode} == CLI_EXIT_CODES


def test_vendor_fact_and_finding_compatibility_fields_remain_present():
    vendor_fields = set(VendorFact.__dataclass_fields__)
    finding_fields = set(Finding.__dataclass_fields__)
    assert set(VENDOR_FACT_REQUIRED_FIELDS).issubset(vendor_fields)
    assert set(FINDING_REQUIRED_FIELDS).issubset(finding_fields)


def test_report_json_compatibility_floor_is_preserved():
    report = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor.pdf",
        findings=[_finding("R0001", Status.PASS)],
    )
    payload = report.to_dict()
    assert set(REPORT_REQUIRED_KEYS).issubset(payload)
    assert payload["tool"] == "bidlint"
    assert payload["counts"] == {"PASS": 1, "DEVIATION": 0, "MISSING": 0, "REVIEW": 0}
    assert payload["findings"][0]["status"] == "PASS"


def test_status_and_scoring_semantics_are_frozen():
    assert tuple(status.value for status in Status) == STATUS_VALUES
    report = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor.pdf",
        findings=[
            _finding("R0001", Status.PASS),
            _finding("R0002", Status.PASS),
            _finding("R0003", Status.DEVIATION),
            _finding("R0004", Status.MISSING),
            _finding("R0005", Status.REVIEW),
        ],
    )
    assert report.compliance_score == 50.0
    assert ComplianceReport("spec.pdf", "vendor.pdf").compliance_score == 0.0
