from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_readiness import write_supplier_response_readiness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-readiness",
        description="Preflight a returned supplier clarification response before buyer review.",
    )
    parser.add_argument("clarification_register", help="original BidLint clarification register JSON")
    parser.add_argument("supplier_response", help="returned supplier clarification response JSON")
    parser.add_argument("output", help="supplier response readiness JSON")
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
        result = write_supplier_response_readiness(register, response, output)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"unable to preflight supplier response: {exc}") from exc
    return 0 if result["ready_for_buyer_review"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
