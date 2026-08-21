from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ExitCode

_REQUIRED_EVIDENCE_KEYS = (
    "tool",
    "pilot_id",
    "mode",
    "passed",
    "deterministic",
    "conformant",
    "report_count",
    "output_digest_sha256",
    "manifest_digest_sha256",
    "corpus_digest_sha256",
)
_COMPARE_FIELDS = (
    "pilot_id",
    "mode",
    "report_count",
    "manifest_digest_sha256",
    "corpus_digest_sha256",
    "output_digest_sha256",
)


@dataclass(frozen=True, slots=True)
class BaselineMismatch:
    field: str
    baseline: object
    current: object

    def to_dict(self) -> dict[str, object]:
        return {"field": self.field, "baseline": self.baseline, "current": self.current}


def validate_evidence_payload(payload: object, *, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} evidence must contain a JSON object")
    missing = [key for key in _REQUIRED_EVIDENCE_KEYS if key not in payload]
    if missing:
        raise ValueError(f"{label} evidence missing required field(s): " + ", ".join(missing))
    if payload["tool"] != "bidlint-pilot":
        raise ValueError(f"{label} evidence tool must equal 'bidlint-pilot'")
    for key in ("pilot_id", "mode", "output_digest_sha256", "manifest_digest_sha256", "corpus_digest_sha256"):
        if not isinstance(payload[key], str) or not payload[key]:
            raise ValueError(f"{label} evidence {key} must be a non-empty string")
    if payload["mode"] not in {"compare", "rank"}:
        raise ValueError(f"{label} evidence mode must be compare or rank")
    for key in ("passed", "deterministic", "conformant"):
        if not isinstance(payload[key], bool):
            raise ValueError(f"{label} evidence {key} must be boolean")
    report_count = payload["report_count"]
    if isinstance(report_count, bool) or not isinstance(report_count, int) or report_count < 1:
        raise ValueError(f"{label} evidence report_count must be a positive integer")
    return payload


def load_evidence(path: str | Path, *, label: str) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {label} evidence {source}: {exc.msg}") from exc
    return validate_evidence_payload(payload, label=label)


def compare_evidence(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> tuple[BaselineMismatch, ...]:
    baseline = validate_evidence_payload(baseline, label="baseline")
    current = validate_evidence_payload(current, label="current")
    if not baseline["passed"] or not baseline["deterministic"] or not baseline["conformant"]:
        raise ValueError("baseline evidence must be passed, deterministic and conformant")

    mismatches: list[BaselineMismatch] = []
    for field in _COMPARE_FIELDS:
        if baseline[field] != current[field]:
            mismatches.append(BaselineMismatch(field, baseline[field], current[field]))

    for field in ("passed", "deterministic", "conformant"):
        if current[field] is not True:
            mismatches.append(BaselineMismatch(field, True, current[field]))
    return tuple(mismatches)


def verification_result(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, object]:
    mismatches = compare_evidence(baseline, current)
    return {
        "tool": "bidlint-pilot-verify",
        "pilot_id": baseline["pilot_id"],
        "match": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": [mismatch.to_dict() for mismatch in mismatches],
        "baseline_output_digest_sha256": baseline["output_digest_sha256"],
        "current_output_digest_sha256": current["output_digest_sha256"],
        "corpus_digest_sha256": current["corpus_digest_sha256"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-pilot-verify",
        description="Compare current BidLint pilot evidence with an approved immutable baseline.",
    )
    parser.add_argument("baseline", help="approved baseline pilot evidence JSON")
    parser.add_argument("current", help="current pilot evidence JSON")
    parser.add_argument("--json", action="store_true", dest="json_output", help="print machine-readable result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        baseline = load_evidence(args.baseline, label="baseline")
        current = load_evidence(args.current, label="current")
        result = verification_result(baseline, current)
    except OSError as exc:
        print(f"unable to read pilot evidence: {exc}", file=sys.stderr)
        return int(ExitCode.IO)
    except ValueError as exc:
        print(f"pilot baseline validation failed: {exc}", file=sys.stderr)
        return int(ExitCode.INPUT)

    if args.json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["match"]:
        print(f"MATCH — {result['pilot_id']}")
        print(f"corpus sha256: {result['corpus_digest_sha256']}")
        print(f"output sha256: {result['current_output_digest_sha256']}")
    else:
        print(f"MISMATCH — {result['pilot_id']}")
        for mismatch in result["mismatches"]:
            print(f"- {mismatch['field']}: baseline={mismatch['baseline']!r} current={mismatch['current']!r}")

    return int(ExitCode.SUCCESS if result["match"] else ExitCode.INPUT)


if __name__ == "__main__":
    raise SystemExit(main())
