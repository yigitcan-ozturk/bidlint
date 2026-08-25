from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_evidence import write_evidence_assessment_template, write_validated_evidence_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-evidence",
        description="Create and validate human evidence-adequacy assessments for supplier clarification responses.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser("template", help="create a buyer evidence-assessment template")
    template.add_argument("supplier_review", help="buyer supplier clarification review JSON")
    template.add_argument("output", help="supplier evidence assessment template JSON")

    validate = subparsers.add_parser("validate", help="validate a completed evidence assessment")
    validate.add_argument("supplier_review", help="buyer supplier clarification review JSON")
    validate.add_argument("assessment", help="completed supplier evidence assessment JSON")
    validate.add_argument("output", help="validated supplier evidence review JSON")
    return parser


def _require_json(path: str, label: str) -> None:
    if Path(path).suffix.lower() != ".json":
        raise SystemExit(f"{label} must end in .json")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "template":
            _require_json(args.supplier_review, "supplier_review")
            _require_json(args.output, "output")
            write_evidence_assessment_template(args.supplier_review, args.output)
        else:
            _require_json(args.supplier_review, "supplier_review")
            _require_json(args.assessment, "assessment")
            _require_json(args.output, "output")
            write_validated_evidence_review(args.supplier_review, args.assessment, args.output)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"unable to process supplier evidence assessment: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
