from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_history import write_appended_history, write_history_validation, write_initialized_history


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-history",
        description="Maintain immutable supplier clarification revisions and surface conflicting technical values.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("init", help="initialize a supplier clarification revision history")
    initialize.add_argument("supplier_review", help="buyer supplier clarification review JSON")
    initialize.add_argument("output", help="supplier clarification history JSON")
    initialize.add_argument("--revision-id", required=True, help="explicit project revision identifier")
    initialize.add_argument("--evidence-review", help="optional validated supplier evidence review JSON")

    append = subparsers.add_parser("append", help="append a revision that supersedes the current active revision")
    append.add_argument("history", help="existing supplier clarification history JSON")
    append.add_argument("supplier_review", help="new buyer supplier clarification review JSON")
    append.add_argument("output", help="updated supplier clarification history JSON")
    append.add_argument("--revision-id", required=True, help="explicit new project revision identifier")
    append.add_argument("--supersedes", required=True, help="active revision identifier being superseded")
    append.add_argument("--evidence-review", help="optional validated supplier evidence review JSON")

    validate = subparsers.add_parser("validate", help="validate revision-chain integrity")
    validate.add_argument("history", help="supplier clarification history JSON")
    validate.add_argument("output", help="history validation result JSON")
    return parser


def _require_json(path: str | None, label: str) -> None:
    if path is not None and Path(path).suffix.lower() != ".json":
        raise SystemExit(f"{label} must end in .json")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            _require_json(args.supplier_review, "supplier_review")
            _require_json(args.output, "output")
            _require_json(args.evidence_review, "evidence_review")
            write_initialized_history(
                args.supplier_review,
                args.output,
                revision_id=args.revision_id,
                evidence_review_path=args.evidence_review,
            )
        elif args.command == "append":
            _require_json(args.history, "history")
            _require_json(args.supplier_review, "supplier_review")
            _require_json(args.output, "output")
            _require_json(args.evidence_review, "evidence_review")
            write_appended_history(
                args.history,
                args.supplier_review,
                args.output,
                revision_id=args.revision_id,
                supersedes_revision_id=args.supersedes,
                evidence_review_path=args.evidence_review,
            )
        else:
            _require_json(args.history, "history")
            _require_json(args.output, "output")
            write_history_validation(args.history, args.output)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"unable to process supplier clarification history: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
