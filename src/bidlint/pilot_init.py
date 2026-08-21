from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .errors import ExitCode

_PILOT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _vendor_count(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 20:
        raise argparse.ArgumentTypeError("vendor count must be between 1 and 20")
    return parsed


def _validate_target(root: Path) -> None:
    if root.is_symlink():
        raise ValueError("pilot workspace path must not be a symlink")
    if root.exists() and not root.is_dir():
        raise ValueError("pilot workspace path exists and is not a directory")
    if root.exists() and any(root.iterdir()):
        raise ValueError("pilot workspace directory must be new or empty")


def _manifest(pilot_id: str, vendor_count: int) -> dict[str, object]:
    vendors = [f"sanitized/vendors/vendor-{index:02d}/vendor.pdf" for index in range(1, vendor_count + 1)]
    return {
        "pilot_id": pilot_id,
        "specification": "sanitized/specification/specification.pdf",
        "vendors": vendors,
        "repeats": 2,
        "options": {
            "threshold": 0.52,
            "aliases": None,
            "knockouts": None,
            "xlsx_sheet": None,
            "ifc_class": None,
            "ifc_guid": None,
            "ifc_pset": None,
        },
    }


def _workspace_readme(pilot_id: str, vendor_count: int) -> str:
    return f"""# BidLint private pilot workspace

Pilot ID: `{pilot_id}`
Vendor slots: {vendor_count}

This workspace is an intake scaffold, not an approved pilot corpus.

## Safe sequence

1. Put original external/customer files only under `raw/`. That directory is git-ignored.
2. Create sanitized technical copies under `sanitized/` using generic file names.
3. Remove identities, contacts, project/customer identifiers, signatures, commercial values and identifying metadata while preserving technical structure needed for evaluation.
4. Run `bidlint-pilot-scan pilot.json --json --output evidence/sanitization-scan.json`.
5. Resolve every BLOCK finding and manually inspect every REVIEW coverage gap.
6. Run `bidlint-pilot pilot.json --json --output evidence/pilot-evidence.json`.
7. Complete `review/TECHNICAL_REVIEW.md` against the sanitized source documents.
8. Convert every reproducible false positive/false negative into a minimized sanitized regression fixture before approving a baseline.
9. Keep raw files, evidence and human review notes private unless they have been separately approved for publication.

The generated `pilot.json` points to placeholder sanitized file paths. Replace or rename those paths deliberately if the real sanitized corpus uses other supported inputs or package directories.
"""


def _sanitization_checklist() -> str:
    return """# Sanitization checklist

This checklist requires a human review even when `bidlint-pilot-scan` reports no automated blockers.

- [ ] Company/vendor/customer names removed or replaced with neutral identifiers.
- [ ] Personal names, emails, phone numbers and postal addresses removed.
- [ ] Project names, job numbers, serial numbers and customer identifiers removed unless technically essential and safely pseudonymized.
- [ ] Prices, currencies, payment terms, delivery/commercial preferences and contractual acceptance wording removed or neutralized.
- [ ] PDF title/author/subject and other identifying metadata stripped.
- [ ] Office document core metadata, comments, hidden content and external links inspected/removed.
- [ ] Embedded files inspected/removed.
- [ ] Drawings, screenshots, photos, stamps, signatures and other visual content manually inspected.
- [ ] Technical units, table geometry, parameter/value relationships and ambiguity patterns required for the test remain intact.
- [ ] Sanitized file names are generic and do not expose the originating customer/project.
- [ ] `bidlint-pilot-scan` has zero BLOCK findings.
- [ ] Remaining REVIEW findings have been inspected and recorded below.

## Manual REVIEW disposition

| Finding category / file | Checked by | Disposition | Notes |
| --- | --- | --- | --- |
|  |  |  |  |

Sanitization approved by: ____________________
Date: ____________________
"""


def _technical_review() -> str:
    return """# Technical pilot review

Complete this after the sanitized corpus passes the automated sanitization gate and `bidlint-pilot` produces deterministic, conformant evidence.

## Evidence

BidLint version / commit: ____________________
Pilot evidence SHA-256 / immutable location: ____________________
Manifest SHA-256: ____________________
Corpus SHA-256: ____________________
Reviewer: ____________________
Date: ____________________

## Findings requiring human review

| Finding / requirement | BidLint status | Source checked | Correct? | Defect / limitation notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Quality register

False positives found: ____________________
False negatives found: ____________________
Unresolved limitations: ____________________
Regression fixtures/tests created: ____________________

## Procurement gate review

- [ ] Explicit knockout policy only; no inferred knockout criteria.
- [ ] DEVIATION outcomes reviewed against source evidence.
- [ ] MISSING outcomes reviewed against the complete declared vendor corpus.
- [ ] REVIEW outcomes retained for genuinely ambiguous/non-deterministic cases.
- [ ] Clarification/deviation/procurement exports are internally consistent when used.
- [ ] No commercial score, price preference, delivery preference or contractual acceptance was introduced.

Technical pilot decision: [ ] APPROVE BASELINE  [ ] BLOCK ROLLOUT  [ ] RE-RUN AFTER FIXES

Reviewer sign-off: ____________________
"""


def _gitignore() -> str:
    return """# Never commit original external/customer material.
raw/

# Pilot evidence may reveal corpus filenames/hashes and stays private by default.
evidence/

# Human review notes may contain project context and stay private by default.
review/

# Local-only overrides or working files.
*.local.json
*.local.md
"""


def initialize_workspace(path: str | Path, *, pilot_id: str, vendor_count: int = 1) -> dict[str, object]:
    if not _PILOT_ID.fullmatch(pilot_id):
        raise ValueError("pilot_id must use 1-80 ASCII letters, digits, '.', '_' or '-' and start alphanumeric")
    if not 1 <= vendor_count <= 20:
        raise ValueError("vendor_count must be between 1 and 20")

    root = Path(path)
    _validate_target(root)
    root.mkdir(parents=True, exist_ok=True)

    (root / "raw").mkdir()
    (root / "sanitized" / "specification").mkdir(parents=True)
    vendors_root = root / "sanitized" / "vendors"
    vendors_root.mkdir(parents=True)
    for index in range(1, vendor_count + 1):
        (vendors_root / f"vendor-{index:02d}").mkdir()
    (root / "evidence").mkdir()
    (root / "review").mkdir()

    manifest = _manifest(pilot_id, vendor_count)
    (root / "pilot.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (root / ".gitignore").write_text(_gitignore(), encoding="utf-8")
    (root / "README.md").write_text(_workspace_readme(pilot_id, vendor_count), encoding="utf-8")
    (root / "SANITIZATION_CHECKLIST.md").write_text(_sanitization_checklist(), encoding="utf-8")
    (root / "review" / "TECHNICAL_REVIEW.md").write_text(_technical_review(), encoding="utf-8")

    return {
        "tool": "bidlint-pilot-init",
        "pilot_id": pilot_id,
        "workspace": str(root),
        "vendor_count": vendor_count,
        "manifest": "pilot.json",
        "raw_gitignored": True,
        "evidence_gitignored": True,
        "review_gitignored": True,
        "ready_for_scan": False,
        "next_step": "populate sanitized inputs, then run bidlint-pilot-scan pilot.json",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-pilot-init",
        description="Create a private-first BidLint external-pilot intake workspace without copying source documents.",
    )
    parser.add_argument("workspace", help="new or empty workspace directory")
    parser.add_argument("--pilot-id", required=True, help="stable non-sensitive pilot identifier")
    parser.add_argument("--vendors", type=_vendor_count, default=1, help="number of vendor slots (1-20; default: 1)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="print machine-readable result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = initialize_workspace(args.workspace, pilot_id=args.pilot_id, vendor_count=args.vendors)
    except ValueError as exc:
        print(f"pilot workspace initialization failed: {exc}", file=sys.stderr)
        return int(ExitCode.CONFIG)
    except OSError as exc:
        print(f"unable to create pilot workspace: {exc}", file=sys.stderr)
        return int(ExitCode.IO)

    if args.json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"CREATED — {result['pilot_id']}")
        print(f"workspace: {result['workspace']}")
        print("raw/, evidence/ and review/ are git-ignored by default")
        print(f"next: {result['next_step']}")
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
