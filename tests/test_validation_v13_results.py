"""Tests for the independent validation manifest evaluator."""
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_v13_results.py"
spec = importlib.util.spec_from_file_location("validate_v13_results", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def case(**changes):
    item = {"id": "S-001", "source_type": "synthetic", "expected": "REVIEW",
            "runs": ["REVIEW", "REVIEW"], "evidence_verified": True}
    item.update(changes)
    return item


def test_matching_runs_pass_but_release_gate_stays_closed():
    result = module.evaluate({"cases": [case()]})
    assert result["passed"] == 1
    assert result["by_source"]["synthetic"]["total"] == 1
    assert result["by_source"]["public"]["total"] == 0
    assert result["release_gate_passed"] is False


def test_wrong_status_fails():
    result = module.evaluate({"cases": [case(runs=["PASS", "PASS"])]})
    assert result["passed"] == 0
    assert result["by_source"]["synthetic"]["incorrect"] == 1


def test_nonrepeatable_fails():
    result = module.evaluate({"cases": [case(runs=["REVIEW", "PASS"])]})
    assert result["cases"][0]["repeatable"] is False


def test_unverified_evidence_fails():
    result = module.evaluate({"cases": [case(evidence_verified=False)]})
    assert result["passed"] == 0


@pytest.mark.parametrize("changes", [
    {"expected": "UNKNOWN"}, {"source_type": "private"}, {"runs": ["PASS"]},
    {"runs": ["REVIEW", "INVALID"]}, {"evidence_verified": "yes"},
])
def test_invalid_case_rejected(changes):
    with pytest.raises(ValueError):
        module.evaluate({"cases": [case(**changes)]})


def test_duplicate_case_id_rejected():
    with pytest.raises(ValueError):
        module.evaluate({"cases": [case(), case()]})


def test_synthetic_selfcheck_fixture_detects_negative_controls():
    import json
    fixture = Path(__file__).resolve().parents[1] / "validation" / "fixtures" / "v13_harness_selfcheck.json"
    result = module.evaluate(json.loads(fixture.read_text(encoding="utf-8")))
    assert result["total"] == 6
    assert result["passed"] == 4
    assert result["by_source"]["synthetic"]["incorrect"] == 2
    assert result["by_source"]["synthetic"]["nonrepeatable"] == 1
    assert result["by_source"]["synthetic"]["unverified_evidence"] == 1
    assert result["release_gate_passed"] is False
