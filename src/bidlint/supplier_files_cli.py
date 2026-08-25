from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_files import write_supplier_evidence_file_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-files",
        description="Bind returned supplier evidence files to a buyer review with exact byte provenance.",
    )
    parser.add_argument("buyer_review", help="supplier clarification buyer-review JSON")
    parser.add_argument("evidence_map", help="local evidence-map JSON describing file bindings")
    parser.add_argument("output", help="supplier evidence file manifest JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for value, label in (
        (args.buyer_review, "buyer_review"),
        (args.evidence_map, "evidence_map"),
        (args.output, "output"),
    ):
        if Path(value).suffix.lower() != ".json":
            raise SystemExit(f"{label} must end in .json")
    try:
        write_supplier_evidence_file_manifest(args.buyer_review, args.evidence_map, args.output)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"unable to build supplier evidence file manifest: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
