from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_pilot import write_pilot_attestation_template, write_portal_readiness
from .supplier_pilot_attested_files import (
    write_pilot_attestation_template_with_files,
    write_portal_readiness_with_files,
)
from .supplier_pilot_files import prepare_pilot_return_with_evidence_files
from .supplier_workspace import write_supplier_workspace_status


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
    prepare.add_argument(
        "--evidence-map",
        help="optional local evidence-map JSON; creates evidence-files.json bound to the buyer review",
    )

    status = subparsers.add_parser(
        "status",
        help="verify a pilot workspace and report its current fail-closed workflow stage",
    )
    status.add_argument("workspace", help="pilot return workspace directory")
    status.add_argument("output", help="supplier workspace status JSON")

    attest = subparsers.add_parser(
        "attestation-template",
        help="create an artifact-bound external-pilot attestation template",
    )
    attest.add_argument("buyer_review", help="validated supplier clarification review JSON")
    attest.add_argument("evidence_review", help="validated supplier evidence review JSON")
    attest.add_argument("history", help="validated supplier clarification history JSON")
    attest.add_argument("output", help="pilot attestation template JSON")
    attest.add_argument(
        "--evidence-files",
        help="supplier evidence-files manifest required when evidence review is file-backed",
    )

    gate = subparsers.add_parser(
        "portal-gate",
        help="evaluate whether real pilot evidence permits hosted-portal scope reconsideration",
    )
    gate.add_argument("buyer_review", help="validated supplier clarification review JSON")
    gate.add_argument("evidence_review", help="validated supplier evidence review JSON")
    gate.add_argument("history", help="validated supplier clarification history JSON")
    gate.add_argument("attestation", help="completed supplier pilot attestation JSON")
    gate.add_argument("output", help="portal readiness result JSON")
    gate.add_argument(
        "--evidence-files",
        help="supplier evidence-files manifest required when evidence review is file-backed",
    )
    return parser


def _require_json(path: str, label: str) -> None:
    if Path(path).suffix.lower() != ".json":
        raise SystemExit(f"{label} must end in .json")


def _evidence_review_requires_files(path: str) -> bool:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("supplier evidence review root must be a JSON object")
    provenance = payload.get("provenance")
    return isinstance(provenance, dict) and isinstance(provenance.get("supplier_evidence_files"), dict)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare-return":
            _require_json(args.clarification_register, "clarification_register")
            _require_json(args.supplier_response, "supplier_response")
            if args.evidence_map:
                _require_json(args.evidence_map, "evidence_map")
            prepare_pilot_return_with_evidence_files(
                args.clarification_register,
                args.supplier_response,
                args.output_dir,
                evidence_map_path=args.evidence_map,
            )
            return 0

        if args.command == "status":
            _require_json(args.output, "output")
            write_supplier_workspace_status(args.workspace, args.output)
            return 0

        if args.command == "attestation-template":
            for value, label in (
                (args.buyer_review, "buyer_review"),
                (args.evidence_review, "evidence_review"),
                (args.history, "history"),
                (args.output, "output"),
            ):
                _require_json(value, label)
            if args.evidence_files:
                _require_json(args.evidence_files, "evidence_files")
                write_pilot_attestation_template_with_files(
                    args.buyer_review,
                    args.evidence_review,
                    args.history,
                    args.evidence_files,
                    args.output,
                )
            else:
                if _evidence_review_requires_files(args.evidence_review):
                    raise ValueError("file-backed supplier evidence review requires --evidence-files manifest")
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
            if args.evidence_files:
                _require_json(args.evidence_files, "evidence_files")
                write_portal_readiness_with_files(
                    args.buyer_review,
                    args.evidence_review,
                    args.history,
                    args.attestation,
                    args.evidence_files,
                    args.output,
                )
            else:
                if _evidence_review_requires_files(args.evidence_review):
                    raise ValueError("file-backed supplier evidence review requires --evidence-files manifest")
                write_portal_readiness(
                    args.buyer_review,
                    args.evidence_review,
                    args.history,
                    args.attestation,
                    args.output,
                )
            return 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"supplier pilot workflow failed: {exc}") from exc

    raise SystemExit("unsupported supplier pilot command")


if __name__ == "__main__":
    raise SystemExit(main())
