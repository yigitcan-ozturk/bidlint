from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .compare import compare
from .parse import parse_requirements, parse_vendor_facts
from .report import portfolio_to_json, to_html, to_json, to_markdown, write_csv


def _summary(report) -> str:
    c = report.counts
    return "\n".join(
        [
            "BIDLINT — TECHNICAL COMPLIANCE",
            "=" * 32,
            f"Score      : {report.compliance_score:.1f}%",
            f"PASS       : {c['PASS']}",
            f"DEVIATION  : {c['DEVIATION']}",
            f"MISSING    : {c['MISSING']}",
            f"REVIEW     : {c['REVIEW']}",
        ]
    )


def _write_report(report, output: str) -> None:
    path = Path(output)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(to_json(report), encoding="utf-8")
    elif suffix in {".md", ".markdown"}:
        path.write_text(to_markdown(report), encoding="utf-8")
    elif suffix == ".html":
        path.write_text(to_html(report), encoding="utf-8")
    elif suffix == ".csv":
        write_csv(report, path)
    else:
        raise SystemExit("--output must end in .json, .md, .html or .csv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint",
        description="Lint technical bids against specifications with source-traceable deterministic rules.",
    )
    parser.add_argument("--version", action="version", version=f"bidlint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    compare_cmd = sub.add_parser("compare", help="compare a specification PDF with one vendor submittal")
    compare_cmd.add_argument("specification")
    compare_cmd.add_argument("vendor")
    compare_cmd.add_argument("--threshold", type=float, default=0.52, help="parameter matching threshold (0-1)")
    compare_cmd.add_argument("--json", action="store_true", help="print machine-readable JSON")
    compare_cmd.add_argument("--markdown", action="store_true", help="print Markdown report")
    compare_cmd.add_argument("--html", action="store_true", help="print self-contained HTML report")
    compare_cmd.add_argument("--output", help="write report to .json, .md, .html or .csv")

    rank_cmd = sub.add_parser("rank", help="compare multiple vendor submittals against one specification")
    rank_cmd.add_argument("specification")
    rank_cmd.add_argument("vendors", nargs="+", help="two or more vendor PDF files")
    rank_cmd.add_argument("--threshold", type=float, default=0.52, help="parameter matching threshold (0-1)")
    rank_cmd.add_argument("--json", action="store_true", help="print portfolio JSON")
    rank_cmd.add_argument("--output", help="write portfolio JSON")

    extract_cmd = sub.add_parser("extract", help="inspect extracted requirements or vendor facts")
    extract_cmd.add_argument("document")
    extract_cmd.add_argument("--kind", choices=["specification", "vendor"], required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "extract":
        items = parse_requirements(args.document) if args.kind == "specification" else parse_vendor_facts(args.document)
        for item in items:
            print(item)
        return 0

    requirements = parse_requirements(args.specification)

    if args.command == "rank":
        if len(args.vendors) < 2:
            raise SystemExit("rank requires at least two vendor PDFs")
        reports = [
            compare(
                requirements,
                parse_vendor_facts(vendor),
                Path(args.specification).name,
                Path(vendor).name,
                threshold=args.threshold,
            )
            for vendor in args.vendors
        ]
        ranked = sorted(
            reports,
            key=lambda r: (-r.compliance_score, r.counts["DEVIATION"] + r.counts["MISSING"], r.vendor.lower()),
        )
        payload = portfolio_to_json(reports)
        if args.output:
            path = Path(args.output)
            if path.suffix.lower() != ".json":
                raise SystemExit("rank --output currently supports .json")
            path.write_text(payload, encoding="utf-8")
        if args.json:
            print(payload)
        else:
            print("BIDLINT — VENDOR RANKING")
            print("=" * 32)
            for index, report in enumerate(ranked, start=1):
                c = report.counts
                print(
                    f"{index:>2}. {report.vendor:<30} {report.compliance_score:>5.1f}%  "
                    f"PASS {c['PASS']}  DEV {c['DEVIATION']}  MISS {c['MISSING']}  REVIEW {c['REVIEW']}"
                )
        return 0

    facts = parse_vendor_facts(args.vendor)
    report = compare(requirements, facts, Path(args.specification).name, Path(args.vendor).name, threshold=args.threshold)

    if args.output:
        _write_report(report, args.output)

    if args.json:
        print(to_json(report))
    elif args.markdown:
        print(to_markdown(report))
    elif args.html:
        print(to_html(report))
    else:
        print(_summary(report))
        for finding in report.findings:
            print(f"{finding.status.value:10} {finding.requirement.id}  {finding.requirement.parameter} — {finding.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
