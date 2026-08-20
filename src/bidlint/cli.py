from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .compare import compare
from .inputs import parse_vendor_input
from .parse import parse_requirements
from .portfolio import portfolio_to_html, portfolio_to_markdown, rank_reports, write_portfolio_csv
from .report import portfolio_to_json, to_html, to_json, to_markdown, write_csv
from .scorecard import write_supplier_scorecard_signal
from .terminology import load_alias_file


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


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


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


def _write_portfolio(reports, output: str) -> None:
    path = Path(output)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(portfolio_to_json(reports), encoding="utf-8")
    elif suffix in {".md", ".markdown"}:
        path.write_text(portfolio_to_markdown(reports), encoding="utf-8")
    elif suffix == ".html":
        path.write_text(portfolio_to_html(reports), encoding="utf-8")
    elif suffix == ".csv":
        write_portfolio_csv(reports, path)
    else:
        raise SystemExit("rank --output must end in .json, .md, .html or .csv")


def _add_matching_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--threshold", type=float, default=0.52, help="parameter matching threshold (0-1)")
    command.add_argument(
        "--aliases",
        metavar="FILE.json",
        help="custom terminology aliases as a JSON object mapping vendor terms to canonical parameters",
    )


def _add_ifc_options(command: argparse.ArgumentParser) -> None:
    group = command.add_argument_group("IFC vendor selection")
    group.add_argument("--ifc-class", help="scope .ifc vendor properties to an IFC class, e.g. IfcPump")
    group.add_argument("--ifc-guid", help="scope .ifc vendor properties to one GlobalId")
    group.add_argument("--ifc-pset", help="optionally restrict IFC properties to one property-set name")


def _ifc_options_supplied(args: argparse.Namespace) -> bool:
    return any(getattr(args, name, None) is not None for name in ("ifc_class", "ifc_guid", "ifc_pset"))


def _parse_cli_vendor(vendor: str, args: argparse.Namespace, *, mixed_rank: bool = False):
    suffix = Path(vendor).suffix.lower()
    if mixed_rank and suffix == ".pdf":
        return parse_vendor_input(vendor)
    return parse_vendor_input(
        vendor,
        ifc_class=getattr(args, "ifc_class", None),
        ifc_guid=getattr(args, "ifc_guid", None),
        ifc_pset=getattr(args, "ifc_pset", None),
    )


def _validate_scorecard_options(args: argparse.Namespace) -> None:
    output = getattr(args, "scorecard_output", None)
    supplier = getattr(args, "supplier_name", None)
    if bool(output) != bool(supplier):
        raise SystemExit("--scorecard-output and --supplier-name must be supplied together")
    if output and Path(output).suffix.lower() != ".json":
        raise SystemExit("--scorecard-output must end in .json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint",
        description="Lint technical bids against specifications with source-traceable deterministic rules.",
    )
    parser.add_argument("--version", action="version", version=f"bidlint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    compare_cmd = sub.add_parser("compare", help="compare a specification PDF with one vendor PDF or IFC input")
    compare_cmd.add_argument("specification")
    compare_cmd.add_argument("vendor")
    _add_matching_options(compare_cmd)
    _add_ifc_options(compare_cmd)
    compare_cmd.add_argument("--json", action="store_true", help="print machine-readable JSON")
    compare_cmd.add_argument("--markdown", action="store_true", help="print Markdown report")
    compare_cmd.add_argument("--html", action="store_true", help="print self-contained HTML report")
    compare_cmd.add_argument("--output", help="write report to .json, .md, .html or .csv")
    compare_cmd.add_argument(
        "--scorecard-output",
        metavar="FILE.json",
        help="write a supplier-scorecard technical-compliance fragment",
    )
    compare_cmd.add_argument(
        "--supplier-name",
        help="supplier name used in --scorecard-output",
    )

    rank_cmd = sub.add_parser("rank", help="compare multiple vendor PDF/IFC inputs against one specification")
    rank_cmd.add_argument("specification")
    rank_cmd.add_argument("vendors", nargs="+", help="two or more vendor PDF/IFC files")
    _add_matching_options(rank_cmd)
    _add_ifc_options(rank_cmd)
    rank_cmd.add_argument("--json", action="store_true", help="print portfolio JSON")
    rank_cmd.add_argument("--top", type=_positive_int, help="show only the top N vendors in terminal output")
    rank_cmd.add_argument("--output", help="write ranking to .json, .md, .html or .csv")

    extract_cmd = sub.add_parser("extract", help="inspect extracted requirements or vendor facts")
    extract_cmd.add_argument("document")
    extract_cmd.add_argument("--kind", choices=["specification", "vendor"], required=True)
    _add_ifc_options(extract_cmd)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "extract":
        try:
            if args.kind == "specification":
                if _ifc_options_supplied(args):
                    raise ValueError("IFC selection options require --kind vendor")
                items = parse_requirements(args.document)
            else:
                items = _parse_cli_vendor(args.document, args)
        except (OSError, RuntimeError, ValueError) as exc:
            raise SystemExit(f"unable to extract {args.kind}: {exc}") from exc
        for item in items:
            print(item)
        return 0

    requirements = parse_requirements(args.specification)
    try:
        aliases = load_alias_file(args.aliases) if args.aliases else None
    except (OSError, ValueError) as exc:
        raise SystemExit(f"unable to load --aliases: {exc}") from exc

    if args.command == "rank":
        if len(args.vendors) < 2:
            raise SystemExit("rank requires at least two vendor inputs")
        if _ifc_options_supplied(args) and not any(Path(vendor).suffix.lower() == ".ifc" for vendor in args.vendors):
            raise SystemExit("IFC selection options require at least one .ifc vendor input")
        reports = []
        for vendor in args.vendors:
            try:
                facts = _parse_cli_vendor(vendor, args, mixed_rank=True)
            except (OSError, RuntimeError, ValueError) as exc:
                raise SystemExit(f"unable to parse vendor input {vendor}: {exc}") from exc
            reports.append(
                compare(
                    requirements,
                    facts,
                    Path(args.specification).name,
                    Path(vendor).name,
                    threshold=args.threshold,
                    aliases=aliases,
                )
            )
        ranked = rank_reports(reports)
        payload = portfolio_to_json(reports)
        if args.output:
            _write_portfolio(reports, args.output)
        if args.json:
            print(payload)
        else:
            print("BIDLINT — VENDOR RANKING")
            print("=" * 32)
            shown = ranked[: args.top] if args.top else ranked
            for index, report in enumerate(shown, start=1):
                c = report.counts
                print(
                    f"{index:>2}. {report.vendor:<30} {report.compliance_score:>5.1f}%  "
                    f"PASS {c['PASS']}  DEV {c['DEVIATION']}  MISS {c['MISSING']}  REVIEW {c['REVIEW']}"
                )
            if len(shown) < len(ranked):
                remaining = len(ranked) - len(shown)
                print(f"... {remaining} more vendor(s); exports remain complete.")
        return 0

    _validate_scorecard_options(args)
    try:
        facts = _parse_cli_vendor(args.vendor, args)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"unable to parse vendor input {args.vendor}: {exc}") from exc
    report = compare(
        requirements,
        facts,
        Path(args.specification).name,
        Path(args.vendor).name,
        threshold=args.threshold,
        aliases=aliases,
    )

    if args.output:
        _write_report(report, args.output)
    if args.scorecard_output:
        try:
            write_supplier_scorecard_signal(report, args.supplier_name, args.scorecard_output)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"unable to write supplier-scorecard signal: {exc}") from exc

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
