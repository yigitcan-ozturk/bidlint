from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .errors import ExitCode
from .pilot import load_manifest
from .pilot_baseline import validate_evidence_payload, verification_result

_REQUIRED_FILES = {
    "scan": Path("evidence/sanitization-scan.json"),
    "baseline": Path("evidence/approved-baseline.json"),
    "replay": Path("evidence/replay-evidence.json"),
    "review": Path("review/approval.json"),
}


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required {label} file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {label} file {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} file must contain a JSON object")
    return payload


def _nonempty(value: object, field: str, failures: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        failures.append(f"{field} must be a non-empty string")
        return None
    return value.strip()


def _iso_date(value: object, field: str, failures: list[str]) -> None:
    text = _nonempty(value, field, failures)
    if text is None:
        return
    try:
        date.fromisoformat(text)
    except ValueError:
        failures.append(f"{field} must be an ISO date (YYYY-MM-DD)")


def _nonnegative_int(value: object, field: str, failures: list[str]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        failures.append(f"{field} must be a non-negative integer")
        return None
    return value


def _require_true(value: object, field: str, failures: list[str]) -> None:
    if value is not True:
        failures.append(f"{field} must be true")


def _validate_scan(payload: dict[str, Any], *, pilot_id: str, failures: list[str]) -> None:
    if payload.get("tool") != "bidlint-pilot-scan":
        failures.append("sanitization scan tool must equal 'bidlint-pilot-scan'")
    if payload.get("pilot_id") != pilot_id:
        failures.append("sanitization scan pilot_id does not match manifest")
    if payload.get("automated_clear") is not True:
        failures.append("sanitization scan must be automated_clear")
    blocker_count = payload.get("blocker_count")
    if isinstance(blocker_count, bool) or not isinstance(blocker_count, int) or blocker_count != 0:
        failures.append("sanitization scan blocker_count must equal 0")
    review_count = payload.get("review_count")
    if isinstance(review_count, bool) or not isinstance(review_count, int) or review_count < 0:
        failures.append("sanitization scan review_count must be a non-negative integer")


def _validate_review(payload: dict[str, Any], *, pilot_id: str, failures: list[str]) -> None:
    if payload.get("tool") != "bidlint-pilot-review":
        failures.append("human review tool must equal 'bidlint-pilot-review'")
    if payload.get("pilot_id") != pilot_id:
        failures.append("human review pilot_id does not match manifest")

    sanitization = payload.get("sanitization")
    if not isinstance(sanitization, dict):
        failures.append("human review sanitization must be an object")
    else:
        _require_true(sanitization.get("approved"), "sanitization.approved", failures)
        _require_true(
            sanitization.get("review_findings_resolved"),
            "sanitization.review_findings_resolved",
            failures,
        )
        _nonempty(sanitization.get("reviewer"), "sanitization.reviewer", failures)
        _iso_date(sanitization.get("reviewed_at"), "sanitization.reviewed_at", failures)

    technical = payload.get("technical")
    if not isinstance(technical, dict):
        failures.append("human review technical must be an object")
        return

    if technical.get("decision") != "APPROVE_BASELINE":
        failures.append("technical.decision must equal 'APPROVE_BASELINE'")
    _nonempty(technical.get("reviewer"), "technical.reviewer", failures)
    _iso_date(technical.get("reviewed_at"), "technical.reviewed_at", failures)
    _require_true(
        technical.get("all_non_pass_findings_reviewed"),
        "technical.all_non_pass_findings_reviewed",
        failures,
    )
    _require_true(technical.get("explicit_knockouts_only"), "technical.explicit_knockouts_only", failures)
    _require_true(technical.get("no_commercial_scoring"), "technical.no_commercial_scoring", failures)

    false_positives = _nonnegative_int(technical.get("false_positive_count"), "technical.false_positive_count", failures)
    false_negatives = _nonnegative_int(technical.get("false_negative_count"), "technical.false_negative_count", failures)
    limitations = _nonnegative_int(
        technical.get("unresolved_limitation_count"),
        "technical.unresolved_limitation_count",
        failures,
    )
    defects = _nonnegative_int(
        technical.get("known_product_defect_count"),
        "technical.known_product_defect_count",
        failures,
    )
    fixtures = _nonnegative_int(
        technical.get("regression_fixtures_created"),
        "technical.regression_fixtures_created",
        failures,
    )

    if limitations is not None and limitations != 0:
        failures.append("technical.unresolved_limitation_count must equal 0 for release readiness")
    if defects is not None and fixtures is not None and fixtures < defects:
        failures.append("technical.regression_fixtures_created must cover every known product defect")
    if false_positives is not None and false_negatives is not None and defects is not None:
        if defects > false_positives + false_negatives:
            failures.append("known product defects cannot exceed recorded false positives plus false negatives")


def evaluate_release_gate(workspace: str | Path) -> dict[str, object]:
    root = Path(workspace)
    if root.is_symlink():
        raise ValueError("pilot workspace must not be a symlink")
    if not root.is_dir():
        raise ValueError(f"pilot workspace is not a directory: {root}")

    manifest, _ = load_manifest(root / "pilot.json")
    scan = _load_json(root / _REQUIRED_FILES["scan"], label="sanitization scan")
    baseline = _load_json(root / _REQUIRED_FILES["baseline"], label="approved baseline")
    replay = _load_json(root / _REQUIRED_FILES["replay"], label="replay evidence")
    review = _load_json(root / _REQUIRED_FILES["review"], label="human review")

    failures: list[str] = []
    _validate_scan(scan, pilot_id=manifest.pilot_id, failures=failures)
    _validate_review(review, pilot_id=manifest.pilot_id, failures=failures)

    try:
        baseline = validate_evidence_payload(baseline, label="baseline")
        replay = validate_evidence_payload(replay, label="replay")
        if baseline.get("pilot_id") != manifest.pilot_id:
            failures.append("baseline pilot_id does not match manifest")
        if replay.get("pilot_id") != manifest.pilot_id:
            failures.append("replay pilot_id does not match manifest")
        verification = verification_result(baseline, replay)
        if verification["match"] is not True:
            fields = ", ".join(item["field"] for item in verification["mismatches"])
            failures.append(f"approved baseline replay mismatch: {fields}")
    except ValueError as exc:
        failures.append(str(exc))
        verification = {"match": False, "mismatch_count": 0, "mismatches": []}

    return {
        "tool": "bidlint-pilot-gate",
        "pilot_id": manifest.pilot_id,
        "release_ready": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "sanitization_automated_clear": scan.get("automated_clear") is True and scan.get("blocker_count") == 0,
        "human_review_approved": not any(
            failure.startswith(("sanitization.", "technical.", "human review")) for failure in failures
        ),
        "baseline_replay_match": verification.get("match") is True,
        "required_files": {name: path.as_posix() for name, path in _REQUIRED_FILES.items()},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-pilot-gate",
        description="Evaluate the explicit external-pilot evidence and human-review gate required before a BidLint release.",
    )
    parser.add_argument("workspace", help="private pilot workspace created with bidlint-pilot-init")
    parser.add_argument("--json", action="store_true", dest="json_output", help="print machine-readable gate result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = evaluate_release_gate(args.workspace)
    except OSError as exc:
        print(f"unable to read pilot gate evidence: {exc}", file=sys.stderr)
        return int(ExitCode.IO)
    except ValueError as exc:
        print(f"pilot release gate failed: {exc}", file=sys.stderr)
        return int(ExitCode.INPUT)

    if args.json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["release_ready"]:
        print(f"RELEASE READY — {result['pilot_id']}")
        print("sanitization: clear + human approved")
        print("baseline replay: match")
    else:
        print(f"BLOCKED — {result['pilot_id']}")
        for failure in result["failures"]:
            print(f"- {failure}")

    return int(ExitCode.SUCCESS if result["release_ready"] else ExitCode.INPUT)


if __name__ == "__main__":
    raise SystemExit(main())
