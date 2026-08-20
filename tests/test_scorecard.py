from __future__ import annotations

import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.cli import main
from bidlint.models import ComplianceReport, Finding, Requirement, Status
from bidlint.scorecard import supplier_scorecard_signal


def _finding(requirement_id: str, status: Status) -> Finding:
    requirement = Requirement(
        id=requirement_id,
        text=f"Requirement {requirement_id}",
        parameter=f"parameter {requirement_id}",
    )
    return Finding(
        requirement=requirement,
        vendor_fact=None,
        status=status,
        confidence=1.0,
        reason=status.value,
    )


def _make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def test_scorecard_signal_emits_numeric_score_when_no_review_remains():
    report = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor.pdf",
        findings=[
            _finding("R0001", Status.PASS),
            _finding("R0002", Status.PASS),
            _finding("R0003", Status.DEVIATION),
            _finding("R0004", Status.MISSING),
        ],
    )

    payload = supplier_scorecard_signal(report, "Supplier A")

    assert payload["contract"] == "supplier-scorecard.technical-compliance"
    assert payload["contract_version"] == "1"
    assert payload["supplier"] == "Supplier A"
    assert payload["technical_compliance"] == 50.0
    assert payload["technical_compliance_status"] == "READY"
    assert payload["technical_compliance_audit"]["counts"] == {
        "PASS": 2,
        "DEVIATION": 1,
        "MISSING": 1,
        "REVIEW": 0,
    }
    assert payload["technical_compliance_audit"]["review_requirement_ids"] == []


def test_scorecard_signal_suppresses_numeric_score_when_review_exists():
    report = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor.pdf",
        findings=[
            _finding("R0001", Status.PASS),
            _finding("R0002", Status.REVIEW),
            _finding("R0003", Status.REVIEW),
        ],
    )

    payload = supplier_scorecard_signal(report, "Supplier A")

    assert payload["technical_compliance"] is None
    assert payload["technical_compliance_status"] == "REVIEW_REQUIRED"
    assert payload["technical_compliance_audit"]["compliance_score"] == 100.0
    assert payload["technical_compliance_audit"]["review_requirement_ids"] == ["R0002", "R0003"]


def test_scorecard_signal_suppresses_empty_report_and_validates_supplier():
    report = ComplianceReport(specification="spec.pdf", vendor="vendor.pdf")
    payload = supplier_scorecard_signal(report, "Supplier A")

    assert payload["technical_compliance"] is None
    assert payload["technical_compliance_status"] == "NO_REQUIREMENTS"

    with pytest.raises(ValueError, match="supplier name is required"):
        supplier_scorecard_signal(report, "   ")


def test_cli_writes_scorecard_fragment_without_changing_normal_report(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    scorecard = tmp_path / "supplier-a-technical.json"
    report_output = tmp_path / "compliance.json"

    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 11 kW"])

    exit_code = main(
        [
            "compare",
            str(specification),
            str(vendor),
            "--json",
            "--output",
            str(report_output),
            "--scorecard-output",
            str(scorecard),
            "--supplier-name",
            "Supplier A",
        ]
    )

    assert exit_code == 0
    normal = json.loads(report_output.read_text(encoding="utf-8"))
    integration = json.loads(scorecard.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)

    assert normal == printed
    assert normal["compliance_score"] == 100.0
    assert integration["supplier"] == "Supplier A"
    assert integration["technical_compliance"] == 100.0
    assert integration["technical_compliance_status"] == "READY"
    assert integration["technical_compliance_audit"]["vendor"] == vendor.name


def test_cli_requires_paired_scorecard_options_and_json_extension(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 11 kW"])

    with pytest.raises(SystemExit, match="must be supplied together"):
        main(
            [
                "compare",
                str(specification),
                str(vendor),
                "--scorecard-output",
                str(tmp_path / "signal.json"),
            ]
        )

    with pytest.raises(SystemExit, match="must end in .json"):
        main(
            [
                "compare",
                str(specification),
                str(vendor),
                "--scorecard-output",
                str(tmp_path / "signal.txt"),
                "--supplier-name",
                "Supplier A",
            ]
        )
