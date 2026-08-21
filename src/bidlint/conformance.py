from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import (
    FINDING_REQUIRED_FIELDS,
    KNOCKOUT_STATUS_VALUES,
    REPORT_REQUIRED_KEYS,
    REQUIREMENT_REQUIRED_FIELDS,
    SOURCE_REF_REQUIRED_FIELDS,
    STATUS_VALUES,
    VENDOR_FACT_REQUIRED_FIELDS,
    stable_contract_manifest,
)
from .errors import ExitCode


@dataclass(frozen=True, slots=True)
class ConformanceIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _add_issue(issues: list[ConformanceIssue], code: str, path: str, message: str) -> None:
    issues.append(ConformanceIssue(code=code, path=path, message=message))


def _require_mapping(
    value: object,
    *,
    path: str,
    issues: list[ConformanceIssue],
) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        _add_issue(issues, "type", path, "must be a JSON object")
        return None
    return value


def _require_fields(
    value: Mapping[str, Any],
    required: tuple[str, ...],
    *,
    path: str,
    issues: list[ConformanceIssue],
) -> None:
    for field in required:
        if field not in value:
            child = f"{path}.{field}" if path else field
            _add_issue(issues, "missing_key", child, "required compatibility field is missing")


def _major_version(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    head = value.split(".", 1)[0]
    if not head.isdigit():
        return None
    return int(head)


def _validate_source(value: object, *, path: str, issues: list[ConformanceIssue]) -> None:
    if value is None:
        return
    source = _require_mapping(value, path=path, issues=issues)
    if source is None:
        return
    _require_fields(source, SOURCE_REF_REQUIRED_FIELDS, path=path, issues=issues)


def _validate_requirement(value: object, *, path: str, issues: list[ConformanceIssue]) -> None:
    requirement = _require_mapping(value, path=path, issues=issues)
    if requirement is None:
        return
    _require_fields(requirement, REQUIREMENT_REQUIRED_FIELDS, path=path, issues=issues)
    if "source" in requirement:
        _validate_source(requirement["source"], path=f"{path}.source", issues=issues)


def _validate_vendor_fact(value: object, *, path: str, issues: list[ConformanceIssue]) -> None:
    if value is None:
        return
    fact = _require_mapping(value, path=path, issues=issues)
    if fact is None:
        return
    _require_fields(fact, VENDOR_FACT_REQUIRED_FIELDS, path=path, issues=issues)
    if "source" in fact:
        _validate_source(fact["source"], path=f"{path}.source", issues=issues)


def _validate_findings(
    value: object,
    *,
    issues: list[ConformanceIssue],
) -> dict[str, int] | None:
    if not isinstance(value, list):
        _add_issue(issues, "type", "findings", "must be a JSON array")
        return None

    observed = {status: 0 for status in STATUS_VALUES}
    for index, item in enumerate(value):
        path = f"findings[{index}]"
        finding = _require_mapping(item, path=path, issues=issues)
        if finding is None:
            continue
        _require_fields(finding, FINDING_REQUIRED_FIELDS, path=path, issues=issues)

        status = finding.get("status")
        if status not in STATUS_VALUES:
            _add_issue(
                issues,
                "invalid_status",
                f"{path}.status",
                f"must be one of {', '.join(STATUS_VALUES)}",
            )
        else:
            observed[str(status)] += 1

        if "requirement" in finding:
            _validate_requirement(finding["requirement"], path=f"{path}.requirement", issues=issues)
        if "vendor_fact" in finding:
            _validate_vendor_fact(finding["vendor_fact"], path=f"{path}.vendor_fact", issues=issues)

    return observed


def _validate_counts(
    value: object,
    *,
    observed: dict[str, int] | None,
    issues: list[ConformanceIssue],
) -> None:
    counts = _require_mapping(value, path="counts", issues=issues)
    if counts is None:
        return

    for status in STATUS_VALUES:
        if status not in counts:
            _add_issue(issues, "missing_key", f"counts.{status}", "status count is required")
            continue
        count = counts[status]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            _add_issue(issues, "type", f"counts.{status}", "must be a non-negative integer")
            continue
        if observed is not None and count != observed[status]:
            _add_issue(
                issues,
                "count_mismatch",
                f"counts.{status}",
                f"declares {count} but findings contain {observed[status]}",
            )


def _expected_score(observed: dict[str, int]) -> float:
    evaluable = observed["PASS"] + observed["DEVIATION"] + observed["MISSING"]
    if evaluable == 0:
        return 0.0
    return round(100.0 * observed["PASS"] / evaluable, 1)


def _validate_score(
    value: object,
    *,
    observed: dict[str, int] | None,
    issues: list[ConformanceIssue],
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _add_issue(issues, "type", "compliance_score", "must be numeric")
        return
    if observed is None:
        return
    expected = _expected_score(observed)
    if abs(float(value) - expected) > 1e-9:
        _add_issue(
            issues,
            "score_mismatch",
            "compliance_score",
            f"declares {value} but stable scoring semantics require {expected}",
        )


def _validate_knockout(value: object, *, issues: list[ConformanceIssue]) -> None:
    knockout = _require_mapping(value, path="knockout", issues=issues)
    if knockout is None:
        return
    status = knockout.get("status")
    if status not in KNOCKOUT_STATUS_VALUES:
        _add_issue(
            issues,
            "invalid_knockout_status",
            "knockout.status",
            f"must be one of {', '.join(KNOCKOUT_STATUS_VALUES)}",
        )


def check_report_payload(payload: object) -> tuple[ConformanceIssue, ...]:
    """Validate a report JSON payload against the BidLint 1.x compatibility floor.

    Unknown additive keys are accepted. The checker focuses on the required 1.x
    surface and on deterministic count/score semantics so that archived reports
    and downstream integrations can be verified without rerunning extraction.
    """

    issues: list[ConformanceIssue] = []
    report = _require_mapping(payload, path="$", issues=issues)
    if report is None:
        return tuple(issues)

    _require_fields(report, REPORT_REQUIRED_KEYS, path="", issues=issues)

    if "tool" in report and report["tool"] != "bidlint":
        _add_issue(issues, "tool", "tool", "must equal 'bidlint'")

    if "version" in report:
        major = _major_version(report["version"])
        if major != 1:
            _add_issue(issues, "version", "version", "must identify a BidLint 1.x report")

    for key in ("specification", "vendor"):
        if key in report and not isinstance(report[key], str):
            _add_issue(issues, "type", key, "must be a string")

    observed = _validate_findings(report.get("findings"), issues=issues) if "findings" in report else None
    if "counts" in report:
        _validate_counts(report["counts"], observed=observed, issues=issues)
    if "compliance_score" in report:
        _validate_score(report["compliance_score"], observed=observed, issues=issues)
    if "knockout" in report:
        _validate_knockout(report["knockout"], issues=issues)

    return tuple(issues)


def load_report_payload(path: str | Path) -> object:
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source}: {exc.msg}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-contract",
        description="Validate BidLint report JSON against the stable 1.x compatibility contract.",
    )
    parser.add_argument("report", nargs="?", help="report JSON file to validate")
    parser.add_argument("--manifest", action="store_true", help="print the machine-readable stable contract manifest")
    parser.add_argument("--json", action="store_true", dest="json_output", help="print machine-readable validation output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.manifest:
        if args.report is not None:
            parser.error("--manifest cannot be combined with a report path")
        print(json.dumps(stable_contract_manifest(), indent=2, sort_keys=True))
        return int(ExitCode.SUCCESS)

    if args.report is None:
        parser.error("a report path or --manifest is required")

    try:
        payload = load_report_payload(args.report)
    except OSError as exc:
        print(f"unable to read report: {exc}", file=sys.stderr)
        return int(ExitCode.IO)
    except ValueError as exc:
        print(f"contract validation failed: {exc}", file=sys.stderr)
        return int(ExitCode.INPUT)

    issues = check_report_payload(payload)
    result = {
        "contract": "bidlint-report-1.x",
        "conformant": not issues,
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
    }
    if args.json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif issues:
        print(f"NON-CONFORMANT — {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue.path}: {issue.message} [{issue.code}]")
    else:
        print("CONFORMANT — BidLint 1.x report contract")

    return int(ExitCode.SUCCESS if not issues else ExitCode.INPUT)


if __name__ == "__main__":
    raise SystemExit(main())
