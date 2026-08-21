import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.cli import main


def make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def write_policy(path: Path, requirement_ids: list[str]) -> None:
    path.write_text(json.dumps({"requirement_ids": requirement_ids}), encoding="utf-8")


def test_compare_cli_emits_knockout_audit(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    policy = tmp_path / "knockouts.json"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11 kW"])
    write_policy(policy, ["R0001"])

    assert main(["compare", str(specification), str(vendor), "--knockouts", str(policy), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["knockout"]["status"] == "ELIGIBLE"
    assert payload["knockout"]["requirement_ids"] == ["R0001"]


def test_rank_cli_applies_same_knockout_policy_to_all_vendors(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor_a = tmp_path / "vendor-a.pdf"
    vendor_b = tmp_path / "vendor-b.pdf"
    policy = tmp_path / "knockouts.json"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor_a, ["Motor power: 11 kW"])
    make_pdf(vendor_b, ["Motor power: 8 kW"])
    write_policy(policy, ["R0001"])

    assert main(
        [
            "rank",
            str(specification),
            str(vendor_b),
            str(vendor_a),
            "--knockouts",
            str(policy),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [item["vendor"] for item in payload["ranking"]] == [vendor_a.name, vendor_b.name]
    assert [item["knockout_status"] for item in payload["ranking"]] == ["ELIGIBLE", "DISQUALIFIED"]


def test_cli_rejects_unknown_knockout_requirement_id(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    policy = tmp_path / "knockouts.json"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11 kW"])
    write_policy(policy, ["R9999"])

    with pytest.raises(SystemExit, match="unknown knockout requirement id"):
        main(["compare", str(specification), str(vendor), "--knockouts", str(policy)])


def test_scorecard_v1_cli_rejects_knockout_assessed_report(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    policy = tmp_path / "knockouts.json"
    scorecard = tmp_path / "scorecard.json"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11 kW"])
    write_policy(policy, ["R0001"])

    with pytest.raises(SystemExit, match="contract v1"):
        main(
            [
                "compare",
                str(specification),
                str(vendor),
                "--knockouts",
                str(policy),
                "--scorecard-output",
                str(scorecard),
                "--supplier-name",
                "Supplier A",
            ]
        )
