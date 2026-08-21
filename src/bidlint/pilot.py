from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cli import main as bidlint_main
from .conformance import ConformanceIssue, check_report_payload
from .errors import ExitCode

_ALLOWED_TOP_LEVEL = {"pilot_id", "specification", "vendors", "repeats", "options"}
_ALLOWED_OPTIONS = {
    "threshold",
    "aliases",
    "knockouts",
    "xlsx_sheet",
    "ifc_class",
    "ifc_guid",
    "ifc_pset",
}


@dataclass(frozen=True, slots=True)
class PilotManifest:
    pilot_id: str
    specification: Path
    vendors: tuple[Path, ...]
    repeats: int
    threshold: float
    aliases: Path | None = None
    knockouts: Path | None = None
    xlsx_sheet: str | None = None
    ifc_class: str | None = None
    ifc_guid: str | None = None
    ifc_pset: str | None = None

    @property
    def mode(self) -> str:
        return "compare" if len(self.vendors) == 1 else "rank"


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, field)


def _relative_path(base: Path, value: object, field: str) -> Path:
    text = _nonempty_string(value, field)
    path = Path(text)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _optional_relative_path(base: Path, value: object, field: str) -> Path | None:
    if value is None:
        return None
    return _relative_path(base, value, field)


def parse_manifest_payload(payload: object, *, base_dir: str | Path) -> PilotManifest:
    if not isinstance(payload, dict):
        raise ValueError("pilot manifest must contain a JSON object")

    unknown = set(payload).difference(_ALLOWED_TOP_LEVEL)
    if unknown:
        raise ValueError("unknown pilot manifest field(s): " + ", ".join(sorted(unknown)))

    required = {"pilot_id", "specification", "vendors"}
    missing = required.difference(payload)
    if missing:
        raise ValueError("missing pilot manifest field(s): " + ", ".join(sorted(missing)))

    base = Path(base_dir).resolve()
    pilot_id = _nonempty_string(payload["pilot_id"], "pilot_id")
    specification = _relative_path(base, payload["specification"], "specification")

    vendors_value = payload["vendors"]
    if not isinstance(vendors_value, list) or not vendors_value:
        raise ValueError("vendors must be a non-empty array")
    vendor_texts = [_nonempty_string(value, f"vendors[{index}]") for index, value in enumerate(vendors_value)]
    vendors = tuple(_relative_path(base, value, f"vendors[{index}]") for index, value in enumerate(vendor_texts))
    if len(set(vendors)) != len(vendors):
        raise ValueError("vendors must not contain duplicate paths")

    repeats = payload.get("repeats", 2)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or not 2 <= repeats <= 10:
        raise ValueError("repeats must be an integer between 2 and 10")

    options_value = payload.get("options", {})
    if not isinstance(options_value, dict):
        raise ValueError("options must be a JSON object")
    unknown_options = set(options_value).difference(_ALLOWED_OPTIONS)
    if unknown_options:
        raise ValueError("unknown pilot option(s): " + ", ".join(sorted(unknown_options)))

    threshold = options_value.get("threshold", 0.52)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0.0 <= float(threshold) <= 1.0:
        raise ValueError("options.threshold must be a number between 0 and 1")

    manifest = PilotManifest(
        pilot_id=pilot_id,
        specification=specification,
        vendors=vendors,
        repeats=repeats,
        threshold=float(threshold),
        aliases=_optional_relative_path(base, options_value.get("aliases"), "options.aliases"),
        knockouts=_optional_relative_path(base, options_value.get("knockouts"), "options.knockouts"),
        xlsx_sheet=_optional_string(options_value.get("xlsx_sheet"), "options.xlsx_sheet"),
        ifc_class=_optional_string(options_value.get("ifc_class"), "options.ifc_class"),
        ifc_guid=_optional_string(options_value.get("ifc_guid"), "options.ifc_guid"),
        ifc_pset=_optional_string(options_value.get("ifc_pset"), "options.ifc_pset"),
    )
    _validate_manifest_paths(manifest)
    return manifest


def load_manifest(path: str | Path) -> tuple[PilotManifest, dict[str, Any]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid pilot JSON in {source}: {exc.msg}") from exc
    manifest = parse_manifest_payload(payload, base_dir=source.parent)
    return manifest, payload


def _validate_manifest_paths(manifest: PilotManifest) -> None:
    if not manifest.specification.is_file():
        raise ValueError(f"specification is not a file: {manifest.specification}")
    for vendor in manifest.vendors:
        if not vendor.exists():
            raise ValueError(f"vendor input does not exist: {vendor}")
        if not (vendor.is_file() or vendor.is_dir()):
            raise ValueError(f"vendor input must be a file or directory: {vendor}")
    for name, path in (("aliases", manifest.aliases), ("knockouts", manifest.knockouts)):
        if path is not None and not path.is_file():
            raise ValueError(f"{name} is not a file: {path}")


def _append_option(args: list[str], flag: str, value: object | None) -> None:
    if value is not None:
        args.extend([flag, str(value)])


def build_bidlint_args(manifest: PilotManifest) -> list[str]:
    if manifest.mode == "compare":
        args = ["compare", str(manifest.specification), str(manifest.vendors[0])]
    else:
        args = ["rank", str(manifest.specification), *(str(vendor) for vendor in manifest.vendors)]

    args.extend(["--json", "--threshold", f"{manifest.threshold:g}"])
    _append_option(args, "--aliases", manifest.aliases)
    _append_option(args, "--knockouts", manifest.knockouts)
    _append_option(args, "--xlsx-sheet", manifest.xlsx_sheet)
    _append_option(args, "--ifc-class", manifest.ifc_class)
    _append_option(args, "--ifc-guid", manifest.ifc_guid)
    _append_option(args, "--ifc-pset", manifest.ifc_pset)
    return args


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _path_evidence(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink():
        raise ValueError(f"pilot corpus must not use symlinked roots: {path}")
    if path.is_file():
        return [(path.name, _hash_file(path))]

    evidence: list[tuple[str, str]] = []
    files = sorted(
        (item for item in path.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(path).as_posix(),
    )
    for child in files:
        if child.is_symlink():
            raise ValueError(f"pilot corpus must not contain symlinked files: {child}")
        evidence.append((child.relative_to(path).as_posix(), _hash_file(child)))
    if not evidence:
        raise ValueError(f"pilot vendor directory is empty: {path}")
    return evidence


def corpus_digest(manifest: PilotManifest) -> tuple[str, list[dict[str, object]]]:
    roots: list[tuple[str, Path]] = [("specification", manifest.specification)]
    roots.extend((f"vendor[{index}]", vendor) for index, vendor in enumerate(manifest.vendors))
    if manifest.aliases is not None:
        roots.append(("aliases", manifest.aliases))
    if manifest.knockouts is not None:
        roots.append(("knockouts", manifest.knockouts))

    records: list[dict[str, object]] = []
    combined = hashlib.sha256()
    for label, path in roots:
        files = _path_evidence(path)
        records.append(
            {
                "label": label,
                "path": path.name,
                "file_count": len(files),
                "files": [{"path": name, "sha256": digest} for name, digest in files],
            }
        )
        for name, digest in files:
            combined.update(label.encode("utf-8"))
            combined.update(b"\0")
            combined.update(name.encode("utf-8"))
            combined.update(b"\0")
            combined.update(digest.encode("ascii"))
            combined.update(b"\n")
    return combined.hexdigest(), records


def _run_once(manifest: PilotManifest) -> object:
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            exit_code = bidlint_main(build_bidlint_args(manifest))
    except SystemExit as exc:
        raise ValueError(f"BidLint pilot execution failed: {exc}") from exc
    if exit_code != 0:
        raise ValueError(f"BidLint pilot execution returned status {exit_code}")

    text = output.getvalue().strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"BidLint pilot produced invalid JSON: {exc.msg}") from exc


def _conformance_issues(payload: object, mode: str) -> tuple[ConformanceIssue, ...]:
    if mode == "compare":
        return check_report_payload(payload)

    if not isinstance(payload, dict):
        return (ConformanceIssue("type", "$", "rank output must be a JSON object"),)
    reports = payload.get("reports")
    if not isinstance(reports, list):
        return (ConformanceIssue("type", "reports", "rank output must contain a reports array"),)

    issues: list[ConformanceIssue] = []
    for index, report in enumerate(reports):
        for issue in check_report_payload(report):
            issues.append(
                ConformanceIssue(
                    code=issue.code,
                    path=f"reports[{index}].{issue.path}",
                    message=issue.message,
                )
            )
    return tuple(issues)


def run_pilot(manifest: PilotManifest, manifest_payload: object) -> dict[str, object]:
    corpus_sha256, corpus_records = corpus_digest(manifest)
    manifest_sha256 = _canonical_digest(manifest_payload)
    run_digests: list[str] = []
    first_payload: object | None = None
    first_issues: tuple[ConformanceIssue, ...] = ()

    for index in range(manifest.repeats):
        payload = _run_once(manifest)
        run_digests.append(_canonical_digest(payload))
        issues = _conformance_issues(payload, manifest.mode)
        if index == 0:
            first_payload = payload
            first_issues = issues
        elif issues != first_issues:
            raise ValueError("conformance result changed between identical pilot runs")

    deterministic = len(set(run_digests)) == 1
    conformant = not first_issues
    report_count = 1
    if manifest.mode == "rank" and isinstance(first_payload, dict) and isinstance(first_payload.get("reports"), list):
        report_count = len(first_payload["reports"])

    return {
        "tool": "bidlint-pilot",
        "pilot_id": manifest.pilot_id,
        "mode": manifest.mode,
        "repeats": manifest.repeats,
        "passed": deterministic and conformant,
        "deterministic": deterministic,
        "conformant": conformant,
        "report_count": report_count,
        "output_digest_sha256": run_digests[0],
        "run_digests_sha256": run_digests,
        "manifest_digest_sha256": manifest_sha256,
        "corpus_digest_sha256": corpus_sha256,
        "corpus": corpus_records,
        "conformance_issue_count": len(first_issues),
        "conformance_issues": [issue.to_dict() for issue in first_issues],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-pilot",
        description="Run a sanitized BidLint pilot repeatedly and produce deterministic conformance evidence.",
    )
    parser.add_argument("manifest", help="pilot manifest JSON")
    parser.add_argument("--json", action="store_true", dest="json_output", help="print machine-readable evidence")
    parser.add_argument("--output", metavar="FILE.json", help="write pilot evidence JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.output and Path(args.output).suffix.lower() != ".json":
        print("pilot validation failed: --output must end in .json", file=sys.stderr)
        return int(ExitCode.CONFIG)

    try:
        manifest, payload = load_manifest(args.manifest)
        result = run_pilot(manifest, payload)
    except OSError as exc:
        print(f"unable to read pilot corpus: {exc}", file=sys.stderr)
        return int(ExitCode.IO)
    except ValueError as exc:
        print(f"pilot validation failed: {exc}", file=sys.stderr)
        return int(ExitCode.INPUT)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        try:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"unable to write pilot evidence: {exc}", file=sys.stderr)
            return int(ExitCode.IO)

    if args.json_output:
        print(rendered)
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} — {manifest.pilot_id}")
        print(f"mode: {manifest.mode}; repeats: {manifest.repeats}; reports: {result['report_count']}")
        print(f"deterministic: {result['deterministic']}; conformant: {result['conformant']}")
        print(f"corpus sha256: {result['corpus_digest_sha256']}")

    return int(ExitCode.SUCCESS if result["passed"] else ExitCode.INPUT)


if __name__ == "__main__":
    raise SystemExit(main())
