from __future__ import annotations

import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.errors import ExitCode
from bidlint.pilot import corpus_digest, load_manifest, main, parse_manifest_payload, run_pilot


def _make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_manifest(specification: str, vendors: list[str]) -> dict:
    return {
        "pilot_id": "pilot-001",
        "specification": specification,
        "vendors": vendors,
        "repeats": 2,
        "options": {"threshold": 0.52},
    }


def test_compare_pilot_is_repeatable_and_conformant(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    manifest_path = tmp_path / "pilot.json"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 12 kW"])
    payload = _base_manifest(specification.name, [vendor.name])
    _write_manifest(manifest_path, payload)

    manifest, loaded = load_manifest(manifest_path)
    result = run_pilot(manifest, loaded)

    assert result["passed"] is True
    assert result["deterministic"] is True
    assert result["conformant"] is True
    assert result["mode"] == "compare"
    assert result["report_count"] == 1
    assert len(set(result["run_digests_sha256"])) == 1
    assert result["conformance_issue_count"] == 0


def test_rank_pilot_validates_each_report(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor_a = tmp_path / "vendor-a.pdf"
    vendor_b = tmp_path / "vendor-b.pdf"
    manifest_path = tmp_path / "pilot.json"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor_a, ["Motor power: 12 kW"])
    _make_pdf(vendor_b, ["Motor power: 8 kW"])
    payload = _base_manifest(specification.name, [vendor_a.name, vendor_b.name])
    _write_manifest(manifest_path, payload)

    manifest, loaded = load_manifest(manifest_path)
    result = run_pilot(manifest, loaded)

    assert result["passed"] is True
    assert result["mode"] == "rank"
    assert result["report_count"] == 2
    assert result["conformance_issue_count"] == 0


def test_manifest_rejects_single_repeat(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 12 kW"])
    payload = _base_manifest(specification.name, [vendor.name])
    payload["repeats"] = 1

    with pytest.raises(ValueError, match="repeats must be an integer between 2 and 10"):
        parse_manifest_payload(payload, base_dir=tmp_path)


def test_manifest_rejects_duplicate_vendor_paths(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 12 kW"])
    payload = _base_manifest(specification.name, [vendor.name, vendor.name])

    with pytest.raises(ValueError, match="vendors must not contain duplicate paths"):
        parse_manifest_payload(payload, base_dir=tmp_path)


def test_manifest_rejects_unknown_option(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 12 kW"])
    payload = _base_manifest(specification.name, [vendor.name])
    payload["options"]["commercial_score"] = 99

    with pytest.raises(ValueError, match="unknown pilot option"):
        parse_manifest_payload(payload, base_dir=tmp_path)


def test_corpus_digest_changes_when_vendor_changes(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    manifest_path = tmp_path / "pilot.json"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 12 kW"])
    payload = _base_manifest(specification.name, [vendor.name])
    _write_manifest(manifest_path, payload)
    manifest, _ = load_manifest(manifest_path)

    first_digest, _ = corpus_digest(manifest)
    _make_pdf(vendor, ["Motor power: 13 kW"])
    second_digest, _ = corpus_digest(manifest)

    assert first_digest != second_digest


def test_cli_writes_pilot_evidence_json(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    manifest_path = tmp_path / "pilot.json"
    output = tmp_path / "evidence.json"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 12 kW"])
    _write_manifest(manifest_path, _base_manifest(specification.name, [vendor.name]))

    assert main([str(manifest_path), "--json", "--output", str(output)]) == ExitCode.SUCCESS
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert file_payload["passed"] is True
    assert file_payload["corpus_digest_sha256"]


def test_cli_returns_input_code_for_invalid_manifest(tmp_path, capsys):
    manifest_path = tmp_path / "pilot.json"
    _write_manifest(manifest_path, {"pilot_id": "pilot-001", "specification": "missing.pdf", "vendors": []})

    assert main([str(manifest_path)]) == ExitCode.INPUT
    assert "pilot validation failed" in capsys.readouterr().err
