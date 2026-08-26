from __future__ import annotations

import argparse
import json
import sys

from .lab_pilot import write_blind_freeze, write_source_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BidLint blind laboratory / technical-furniture pilot controls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_manifest = subparsers.add_parser(
        "source-manifest",
        help="Bind local confidential source bytes to anonymous source IDs without persisting names or paths",
    )
    source_manifest.add_argument("source_map")
    source_manifest.add_argument("output")

    blind_freeze = subparsers.add_parser(
        "blind-freeze",
        help="Freeze blind technical/commercial/material-fit artifacts before buyer identity reveal",
    )
    blind_freeze.add_argument("freeze_map")
    blind_freeze.add_argument("output")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "source-manifest":
            result = write_source_manifest(args.source_map, args.output)
        else:
            result = write_blind_freeze(args.freeze_map, args.output)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"bidlint-lab-pilot: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"contract": result["contract"], "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
