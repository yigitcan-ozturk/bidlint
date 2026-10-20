"""Offline validation of independently reviewed BidLint case results.

Input is a JSON manifest. This script does not execute BidLint or assign gold labels.
Each case requires reviewer-provided expectations and run observations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

STATUSES = {"PASS", "DEVIATION", "MISSING", "REVIEW"}
SOURCES = {"public", "consented", "synthetic"}


def evaluate(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        raise ValueError("manifest must contain a cases list")
    results = []
    seen = set()
    for case in manifest["cases"]:
        if not isinstance(case, dict):
            raise ValueError("case must be an object")
        case_id = case.get("id")
        source = case.get("source_type")
        expected = case.get("expected")
        runs = case.get("runs")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("case id must be unique and nonempty")
        seen.add(case_id)
        if source not in SOURCES or expected not in STATUSES:
            raise ValueError(f"{case_id}: invalid source type or expected status")
        if not isinstance(runs, list) or len(runs) < 2 or any(r not in STATUSES for r in runs):
            raise ValueError(f"{case_id}: at least two valid run statuses required")
        evidence = case.get("evidence_verified")
        if not isinstance(evidence, bool):
            raise ValueError(f"{case_id}: evidence_verified must be boolean")
        repeatable = len(set(runs)) == 1
        correct = all(r == expected for r in runs)
        results.append({"id": case_id, "source_type": source, "expected": expected,
                        "runs": runs, "correct": correct, "repeatable": repeatable,
                        "evidence_verified": evidence,
                        "passed": correct and repeatable and evidence})
    summary = {}
    for source in sorted(SOURCES):
        subset = [r for r in results if r["source_type"] == source]
        summary[source] = {"total": len(subset), "passed": sum(r["passed"] for r in subset),
                           "incorrect": sum(not r["correct"] for r in subset),
                           "nonrepeatable": sum(not r["repeatable"] for r in subset),
                           "unverified_evidence": sum(not r["evidence_verified"] for r in subset)}
    return {"schema_version": 1, "total": len(results), "passed": sum(r["passed"] for r in results),
            "by_source": summary, "cases": results,
            "release_gate_passed": False,
            "note": "This status-only harness cannot verify evidence locators, file hashes, or regression gates."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if result["total"] and result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
