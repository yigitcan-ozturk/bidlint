from __future__ import annotations

import json

from bidlint.errors import ExitCode
from bidlint.pilot_gate import evaluate_release_gate, main


def _evidence(*, repeats: int = 2, output: str = "out-aaa", corpus: str = "corpus-aaa") -> dict:
    return {
        "tool": "bidlint-pilot",
        "pilot_id": "external-pilot-001",
        "mode": "compare",
        "repeats": repeats,
        "passed": True,
        "deterministic": True,
        "conformant": True,
        "report_count": 1,
        "output_digest_sha256": output,
        "run_digests_sha256": [output] * repeats,
        "manifest_digest_sha256": "manifest-aaa",
        "corpus_digest_sha256": corpus,
        "corpus": [],
        "conformance_issue_count": 0,
        "conformance_issues": [],
    }


def _review(**technical_overrides) -> dict:
    technical = {
        "decision": "APPROVE_BASELINE",
        "reviewer": "Domain Reviewer",
        "reviewed_at": "2026-08-21",
        "all_non_pass_findings_reviewed": True,
        "false_positive_count": 0,
        "false_negative_count": 0,
        "unresolved_limitation_count": 0,
        "known_product_defect_count": 0,
        "regression_fixtures_created": 0,
        "explicit_knockouts_only": True,
        "no_commercial_scoring": True,
    }
    technical.update(technical_overrides)
    return {
        "tool": "bidlint-pilot-review",
        "pilot_id": "external-pilot-001",
        "sanitization": {
            "approved": True,
            "reviewer": "Sanitization Reviewer",
            "reviewed_at": "2026-08-21",
            "review_findings_resolved": True,
        },
        "technical": technical,
    }


def _workspace(tmp_path, *, scan=None, baseline=None, replay=None, review=None):
    root = tmp_path / "pilot"
    (root / "sanitized" / "specification").mkdir(parents=True)
    (root / "sanitized" / "vendors" / "vendor-01").mkdir(parents=True)
    (root / "evidence").mkdir()
    (root / "review").mkdir()
    (root / "sanitized" / "specification" / "specification.pdf").write_bytes(b"placeholder")
    (root / "sanitized" / "vendors" / "vendor-01" / "vendor.pdf").write_bytes(b"placeholder")
    (root / "pilot.json").write_text(
        json.dumps(
            {
                "pilot_id": "external-pilot-001",
                "specification": "sanitized/specification/specification.pdf",
                "vendors": ["sanitized/vendors/vendor-01/vendor.pdf"],
                "repeats": 2,
            }
        ),
        encoding="utf-8",
    )
    scan = scan or {
        "tool": "bidlint-pilot-scan",
        "pilot_id": "external-pilot-001",
        "automated_clear": True,
        "manual_review_required": True,
        "files_scanned": 3,
        "blocker_count": 0,
        "review_count": 2,
        "findings": [],
        "limitations": [],
    }
    (root / "evidence" / "sanitization-scan.json").write_text(json.dumps(scan), encoding="utf-8")
    (root / "evidence" / "approved-baseline.json").write_text(json.dumps(baseline or _evidence()), encoding="utf-8")
    (root / "evidence" / "replay-evidence.json").write_text(
        json.dumps(replay or _evidence(repeats=4)), encoding="utf-8"
    )
    (root / "review" / "approval.json").write_text(json.dumps(review or _review()), encoding="utf-8")
    return root


def test_release_gate_passes_only_with_explicit_human_approval_and_matching_replay(tmp_path):
    root = _workspace(tmp_path)

    result = evaluate_release_gate(root)

    assert result["release_ready"] is True
    assert result["failure_count"] == 0
    assert result["baseline_replay_match"] is True


def test_release_gate_blocks_unapproved_sanitization(tmp_path):
    review = _review()
    review["sanitization"]["approved"] = False
    root = _workspace(tmp_path, review=review)

    result = evaluate_release_gate(root)

    assert result["release_ready"] is False
    assert "sanitization.approved must be true" in result["failures"]


def test_release_gate_blocks_baseline_replay_mismatch(tmp_path):
    root = _workspace(tmp_path, replay=_evidence(repeats=4, corpus="corpus-changed"))

    result = evaluate_release_gate(root)

    assert result["release_ready"] is False
    assert any("approved baseline replay mismatch" in failure for failure in result["failures"])


def test_release_gate_blocks_scan_with_automated_blockers(tmp_path):
    scan = {
        "tool": "bidlint-pilot-scan",
        "pilot_id": "external-pilot-001",
        "automated_clear": False,
        "manual_review_required": True,
        "files_scanned": 3,
        "blocker_count": 1,
        "review_count": 1,
        "findings": [],
        "limitations": [],
    }
    root = _workspace(tmp_path, scan=scan)

    result = evaluate_release_gate(root)

    assert result["release_ready"] is False
    assert "sanitization scan must be automated_clear" in result["failures"]
    assert "sanitization scan blocker_count must equal 0" in result["failures"]


def test_release_gate_blocks_unresolved_limitations_and_uncovered_defects(tmp_path):
    review = _review(
        false_positive_count=1,
        false_negative_count=1,
        unresolved_limitation_count=1,
        known_product_defect_count=2,
        regression_fixtures_created=1,
    )
    root = _workspace(tmp_path, review=review)

    result = evaluate_release_gate(root)

    assert result["release_ready"] is False
    assert "technical.unresolved_limitation_count must equal 0 for release readiness" in result["failures"]
    assert "technical.regression_fixtures_created must cover every known product defect" in result["failures"]


def test_release_gate_rejects_inferred_knockouts_or_commercial_scoring(tmp_path):
    root = _workspace(tmp_path, review=_review(explicit_knockouts_only=False, no_commercial_scoring=False))

    result = evaluate_release_gate(root)

    assert result["release_ready"] is False
    assert "technical.explicit_knockouts_only must be true" in result["failures"]
    assert "technical.no_commercial_scoring must be true" in result["failures"]


def test_cli_returns_input_when_gate_is_blocked(tmp_path, capsys):
    root = _workspace(tmp_path, review=_review(decision="RE_RUN_AFTER_FIXES"))

    exit_code = main([str(root), "--json"])

    assert exit_code == int(ExitCode.INPUT)
    payload = json.loads(capsys.readouterr().out)
    assert payload["release_ready"] is False
    assert payload["failure_count"] == 1


def test_gate_requires_explicit_review_file(tmp_path):
    root = _workspace(tmp_path)
    (root / "review" / "approval.json").unlink()

    try:
        evaluate_release_gate(root)
    except ValueError as exc:
        assert "missing required human review file" in str(exc)
    else:
        raise AssertionError("gate should reject missing human review evidence")
