from __future__ import annotations

import argparse
from pathlib import Path

from .supplier_pilot import prepare_pilot_return, write_pilot_attestation_template, write_portal_readiness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-pilot",
        description="Execute and gate the external supplier clarification pilot workflow.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare-return",
        help="ingest a returned supplier response and create buyer-review/evidence-assessment artifacts",
    )
    prepare.add_argument("clarification_register", help="source clarification register JSON")
    prepare.add_argument("supplier_response", help="returned supplier response JSON")
    prepare.add_argument("output_dir", help="new directory for pilot return artifacts")

    attest = subparsers.add_parser(
        "attestation-template",
        help="create an artifact-bound external-pilot attestation template",
    )
    attest.add_argument("buyer_review", help="validated supplier clarification review JSON")
    attest.add_argument("evidence_review", help="validated supplier evidence review JSON")
    attest.add_argument("history", help="validated supplier clarification history JSON")
    attest.add_argument("output", help="pilot attestation template JSON")

    gate = subparsers.add_parser(
        "portal-gate",
        help="evaluate whether real pilot evidence permits hosted-portal scope reconsideration",
    )
    gate.add_argument("buyer_review", help="validated supplier clarification review JSON")
    gate.add_argument("evidence_review", help="validated supplier evidence review JSON")
    gate.add_argument("history", help="validated supplier clarification history JSON")
    gate.add_argument("attestation", help="completed supplier pilot attestation JSON")
    gate.add_argument("output", help="portal readiness result JSON")
    return parser


def _require_json(path: str, label: str) -> None:
    if Path(path).suffix.lower() != ".json":
        raise SystemExit(f"{label} must end in .json")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare-return":
            _require_json(args.clarification_register, "clarification_register")
            _require_json(args.supplier_response, "supplier_response")
            prepare_pilot_return(args.clarification_register, args.supplier_response, args.output_dir)
            return 0

        if args.command == "attestation-template":
            for value, label in (
                (args.buyer_review, "buyer_review"),
                (args.evidence_review, "evidence_review"),
                (args.history, "history"),
                (args.output, "output"),
            ):
                _require_json(value, label)
            write_pilot_attestation_template(args.buyer_review, args.evidence_review, args.history, args.output)
            return 0

        if args.command == "portal-gate":
            for value, label in (
                (args.buyer_review, "buyer_review"),
                (args.evidence_review, "evidence_review"),
                (args.history, "history"),
                (args.attestation, "attestation"),
                (args.output, "output"),
            ):
                _require_json(value, label)
            write_portal_readiness(
                args.buyer_review,
                args.evidence_review,
                args.history,
                args.attestation,
                args.output,
            )
            return 0
    except (OSError, ValueError) as exc:
        raise SystemExit(f"supplier pilot workflow failed: {exc}") from exc

    raise SystemExit("unsupported supplier pilot command")


if __name__ == "__main__":
    raise SystemExit(main())
