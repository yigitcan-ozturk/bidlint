from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_response import write_supplier_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-review",
        description="Ingest a supplier clarification response into a provenance-preserving buyer review package.",
    )
    parser.add_argument("clarification_register", help="original BidLint clarification register JSON")
    parser.add_argument("supplier_response", help="supplier clarification response JSON")
    parser.add_argument("output", help="buyer-side review package JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    register = Path(args.clarification_register)
    response = Path(args.supplier_response)
    output = Path(args.output)
    for label, path in (
        ("clarification_register", register),
        ("supplier_response", response),
        ("output", output),
    ):
        if path.suffix.lower() != ".json":
            raise SystemExit(f"{label} must end in .json")

    try:
        write_supplier_review(register, response, output)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"unable to ingest supplier response: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
