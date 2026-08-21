from __future__ import annotations

import json

import pytest

from bidlint.errors import ExitCode
from bidlint.pilot_baseline import compare_evidence, main, verification_result


def _evidence(**overrides) -> dict:
    payload = {
        "tool": "bidlint-pilot",
        "pilot_id": "pilot-001",
        "mode": "compare",
        "repeats": 2,
        "passed": True,
        "deterministic": True,
        "conformant": True,
        "report_count": 1,
        "output_digest_sha256": "out-aaa",
        "run_digests_sha256": ["out-aaa", "out-aaa"],
        "manifest_digest_sha256": "manifest-aaa",
        "corpus_digest_sha256": "corpus-aaa",
        "corpus": [],
        "conformance_issue_count": 0,
        "conformance_issues": [],
    }
    payload.update(overrides)
    return payload


def test_identical_successful_evidence_matches():
    baseline = _evidence()
    current = _evidence(repeats=5)

    assert compare_evidence(baseline, current) == ()
    result = verification_result(baseline, current)
    assert result["match"] is True
    assert result["mismatch_count"] == 0


def test_output_digest_change_is_reported():
    mismatches = compare_evidence(_evidence(), _evidence(output_digest_sha256="out-bbb"))

    assert [item.field for item in mismatches] == ["output_digest_sha256"]


def test_corpus_change_is_reported_separately():
    mismatches = compare_evidence(_evidence(), _evidence(corpus_digest_sha256="corpus-bbb"))

    assert [item.field for item in mismatches] == ["corpus_digest_sha256"]


def test_current_nonconformance_is_a_mismatch():
    mismatches = compare_evidence(_evidence(), _evidence(passed=False, conformant=False))

    fields = {item.field for item in mismatches}
    assert fields == {"passed", "conformant"}


def test_unsuccessful_baseline_is_rejected():
    with pytest.raises(ValueError, match="baseline evidence must be passed"):
        compare_evidence(_evidence(passed=False), _evidence())


def test_cli_exact_baseline_returns_success(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    current_path.write_text(json.dumps(_evidence(repeats=4)), encoding="utf-8")

    assert main([str(baseline_path), str(current_path), "--json"]) == ExitCode.SUCCESS
    result = json.loads(capsys.readouterr().out)
    assert result["match"] is True


def test_cli_mismatch_returns_input_exit_code(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    current_path.write_text(json.dumps(_evidence(output_digest_sha256="changed")), encoding="utf-8")

    assert main([str(baseline_path), str(current_path), "--json"]) == ExitCode.INPUT
    result = json.loads(capsys.readouterr().out)
    assert result["match"] is False
    assert result["mismatch_count"] == 1
