import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.cli import main


def _make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def _write_policy(path: Path, requirement_ids: list[str]) -> None:
    path.write_text(json.dumps({"requirement_ids": requirement_ids}), encoding="utf-8")


def test_compare_cli_writes_procurement_artifacts_and_scorecard_v2(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    policy = tmp_path / "knockouts.json"
    clarifications = tmp_path / "clarifications.json"
    deviations = tmp_path / "deviations.json"
    procurement = tmp_path / "procurement.json"
    scorecard = tmp_path / "scorecard.json"

    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 8 kW"])
    _write_policy(policy, ["R0001"])

    exit_code = main(
        [
            "compare",
            str(specification),
            str(vendor),
            "--knockouts",
            str(policy),
            "--clarifications-output",
            str(clarifications),
            "--deviations-output",
            str(deviations),
            "--procurement-output",
            str(procurement),
            "--scorecard-output",
            str(scorecard),
            "--supplier-name",
            "Supplier A",
            "--scorecard-contract",
            "2",
        ]
    )

    assert exit_code == 0
    assert json.loads(clarifications.read_text())["counts"]["open_items"] == 0
    assert json.loads(deviations.read_text())["counts"]["deviations"] == 1
    assert json.loads(procurement.read_text())["status"] == "DISQUALIFIED"
    scorecard_payload = json.loads(scorecard.read_text())
    assert scorecard_payload["contract_version"] == "2"
    assert scorecard_payload["technical_compliance"] is None
    assert scorecard_payload["technical_compliance_status"] == "DISQUALIFIED"


def test_rank_cli_procurement_output_ranks_only_ready_supplier(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor_a = tmp_path / "vendor-a.pdf"
    vendor_b = tmp_path / "vendor-b.pdf"
    policy = tmp_path / "knockouts.json"
    procurement = tmp_path / "procurement.json"

    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor_a, ["Motor power: 11 kW"])
    _make_pdf(vendor_b, ["Motor power: 8 kW"])
    _write_policy(policy, ["R0001"])

    exit_code = main(
        [
            "rank",
            str(specification),
            str(vendor_b),
            str(vendor_a),
            "--knockouts",
            str(policy),
            "--procurement-output",
            str(procurement),
        ]
    )

    assert exit_code == 0
    payload = json.loads(procurement.read_text())
    assert [item["vendor"] for item in payload["ready_ranking"]] == [vendor_a.name]
    assert [item["vendor"] for item in payload["excluded"]] == [vendor_b.name]
    assert payload["excluded"][0]["status"] == "DISQUALIFIED"


def test_procurement_output_options_require_json_extension(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 11 kW"])

    with pytest.raises(SystemExit, match="clarifications-output must end in .json"):
        main(
            [
                "compare",
                str(specification),
                str(vendor),
                "--clarifications-output",
                str(tmp_path / "clarifications.txt"),
            ]
        )
