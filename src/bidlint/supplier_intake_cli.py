from __future__ import annotations

import argparse
import json
from pathlib import Path

from .supplier_intake import write_supplier_intake_from_register


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-supplier-intake",
        description="Convert a BidLint clarification register into an offline supplier response form.",
    )
    parser.add_argument("clarification_register", help="BidLint clarification register JSON")
    parser.add_argument("output", help="self-contained supplier response form (.html)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(args.clarification_register)
    output = Path(args.output)
    if source.suffix.lower() != ".json":
        raise SystemExit("clarification_register must end in .json")
    if output.suffix.lower() != ".html":
        raise SystemExit("output must end in .html")

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("clarification register root must be a JSON object")
        write_supplier_intake_from_register(payload, output)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"unable to create supplier intake form: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
