from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .clarifications import write_clarification_portfolio, write_clarification_register
from .compare import compare
from .deviations import write_procurement_review_portfolio, write_procurement_review_register
from .document_policy import classify_document, is_evidence_class
from .inputs import parse_vendor_input
from .knockout import apply_knockouts, load_knockout_file, validate_knockout_requirement_ids
from .parse import parse_requirements
from .portfolio import portfolio_to_html, portfolio_to_markdown, rank_reports, write_portfolio_csv
from .procurement import write_procurement_portfolio, write_procurement_readiness
from .report import portfolio_to_json, to_html, to_json, to_markdown, write_csv
from .scorecard import write_supplier_scorecard_signal, write_supplier_scorecard_signal_v2
from .terminology import load_alias_file
from .xlsx import write_portfolio_xlsx


def _summary(report) -> str:
    c = report.counts
    lines = [
        "BIDLINT — TECHNICAL COMPLIANCE",
        "=" * 32,
        f"Score      : {report.compliance_score:.1f}%",
        f"PASS       : {c['PASS']}",
        f"DEVIATION  : {c['DEVIATION']}",
        f"MISSING    : {c['MISSING']}",
        f"REVIEW     : {c['REVIEW']}",
    ]
    if report.knockout is not None:
        lines.append(f"Knockout   : {report.knockout.status.value}")
    return "\n".join(lines)


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
    elif suffix == ".xlsx":
        write_portfolio_xlsx(reports, path)
    else:
        raise SystemExit("rank --output must end in .json, .md, .html, .csv or .xlsx")


def _add_matching_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--threshold", type=float, default=0.52, help="parameter matching threshold (0-1)")
    command.add_argument(
        "--aliases",
        metavar="FILE.json",
        help="custom terminology aliases as a JSON object mapping vendor terms to canonical parameters",
    )


def _add_procurement_options(command: argparse.ArgumentParser) -> None:
    group = command.add_argument_group("procurement workflow")
    group.add_argument(
        "--knockouts",
        metavar="FILE.json",
        help="explicit knockout policy JSON containing requirement_ids",
    )
    group.add_argument(
        "--clarifications-output",
        metavar="FILE.json",
        help="write bidder clarifications and unanswered requirements as JSON",
    )
    group.add_argument(
        "--deviations-output",
        metavar="FILE.json",
        help="write deviations and internal technical review queue as JSON",
    )
    group.add_argument(
        "--procurement-output",
        metavar="FILE.json",
        help="write procurement readiness or ready-only portfolio ranking as JSON",
    )


def _add_ifc_options(command: argparse.ArgumentParser) -> None:
    group = command.add_argument_group("IFC vendor selection")
    group.add_argument("--ifc-class", help="scope .ifc vendor properties to an IFC class, e.g. IfcPump")
    group.add_argument("--ifc-guid", help="scope .ifc vendor properties to one GlobalId")
    group.add_argument("--ifc-pset", help="optionally restrict IFC properties to one property-set name")


def _add_xlsx_options(command: argparse.ArgumentParser) -> None:
    group = command.add_argument_group("XLSX vendor selection")
    group.add_argument(
        "--xlsx-sheet",
        help="select one visible worksheet when a vendor .xlsx contains multiple visible sheets",
    )


def _ifc_options_supplied(args: argparse.Namespace) -> bool:
    return any(getattr(args, name, None) is not None for name in ("ifc_class", "ifc_guid", "ifc_pset"))


def _xlsx_options_supplied(args: argparse.Namespace) -> bool:
    return getattr(args, "xlsx_sheet", None) is not None


def _vendor_has_evidence_suffix(vendor: str, suffix: str) -> bool:
    path = Path(vendor)
    normalized_suffix = suffix.lower()
    if path.is_dir():
        return any(
            child.is_file()
            and child.suffix.lower() == normalized_suffix
            and is_evidence_class(classify_document(child))
            for child in path.iterdir()
        )
    return path.suffix.lower() == normalized_suffix


def _parse_cli_vendor(vendor: str, args: argparse.Namespace, *, mixed_rank: bool = False, aliases=None):
    path = Path(vendor)
    if mixed_rank and path.is_dir():
        has_ifc = _vendor_has_evidence_suffix(vendor, ".ifc")
        has_xlsx = _vendor_has_evidence_suffix(vendor, ".xlsx")
        return parse_vendor_input(
            vendor,
            ifc_class=getattr(args, "ifc_class", None) if has_ifc else None,
            ifc_guid=getattr(args, "ifc_guid", None) if has_ifc else None,
            ifc_pset=getattr(args, "ifc_pset", None) if has_ifc else None,
            xlsx_sheet=getattr(args, "xlsx_sheet", None) if has_xlsx else None,
            aliases=aliases,
        )

    suffix = path.suffix.lower()
    if mixed_rank:
        if suffix == ".pdf":
            return parse_vendor_input(vendor)
        if suffix == ".xlsx":
            return parse_vendor_input(vendor, xlsx_sheet=getattr(args, "xlsx_sheet", None))
        if suffix == ".ifc":
            return parse_vendor_input(
                vendor,
                ifc_class=getattr(args, "ifc_class", None),
                ifc_guid=getattr(args, "ifc_guid", None),
                ifc_pset=getattr(args, "ifc_pset", None),
            )
    return parse_vendor_input(
        vendor,
        ifc_class=getattr(args, "ifc_class", None),
        ifc_guid=getattr(args, "ifc_guid", None),
        ifc_pset=getattr(args, "ifc_pset", None),
        xlsx_sheet=getattr(args, "xlsx_sheet", None),
        aliases=aliases,
    )


def _validate_scorecard_options(args: argparse.Namespace) -> None:
    output = getattr(args, "scorecard_output", None)
    supplier = getattr(args, "supplier_name", None)
    if bool(output) != bool(supplier):
        raise SystemExit("--scorecard-output and --supplier-name must be supplied together")
    if output and Path(output).suffix.lower() != ".json":
        raise SystemExit("--scorecard-output must end in .json")


def _validate_procurement_outputs(args: argparse.Namespace) -> None:
    for option in ("clarifications_output", "deviations_output", "procurement_output"):
        value = getattr(args, option, None)
        if value and Path(value).suffix.lower() != ".json":
            flag = "--" + option.replace("_", "-")
            raise SystemExit(f"{flag} must end in .json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint",
        description="Lint technical bids against specifications with source-traceable deterministic rules.",
    )
    parser.add_argument("--version", action="version", version=f"bidlint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    compare_cmd = sub.add_parser(
        "compare",
        help="compare a specification PDF with one vendor file or package directory",
    )
    compare_cmd.add_argument("specification")
    compare_cmd.add_argument("vendor")
    _add_matching_options(compare_cmd)
    _add_procurement_options(compare_cmd)
    _add_ifc_options(compare_cmd)
    _add_xlsx_options(compare_cmd)
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
    compare_cmd.add_argument(
        "--scorecard-contract",
        choices=["1", "2"],
        default="1",
        help="supplier-scorecard contract version (default: 1; use 2 for procurement-aware hand-off)",
    )

    rank_cmd = sub.add_parser(
        "rank",
        help="compare multiple vendor files or package directories against one specification",
    )
    rank_cmd.add_argument("specification")
    rank_cmd.add_argument("vendors", nargs="+", help="two or more vendor files or package directories")
    _add_matching_options(rank_cmd)
    _add_procurement_options(rank_cmd)
    _add_ifc_options(rank_cmd)
    _add_xlsx_options(rank_cmd)
    rank_cmd.add_argument("--json", action="store_true", help="print portfolio JSON")
    rank_cmd.add_argument("--top", type=_positive_int, help="show only the top N vendors in terminal output")
    rank_cmd.add_argument("--output", help="write ranking to .json, .md, .html, .csv or .xlsx")

    extract_cmd = sub.add_parser("extract", help="inspect extracted requirements or vendor facts")
    extract_cmd.add_argument("document")
    extract_cmd.add_argument("--kind", choices=["specification", "vendor"], required=True)
    _add_ifc_options(extract_cmd)
    _add_xlsx_options(extract_cmd)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "extract":
        try:
            if args.kind == "specification":
                if _ifc_options_supplied(args):
                    raise ValueError("IFC selection options require --kind vendor")
                if _xlsx_options_supplied(args):
                    raise ValueError("--xlsx-sheet requires --kind vendor")
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

    try:
        knockout_ids = load_knockout_file(args.knockouts) if args.knockouts else None
        if knockout_ids is not None:
            knockout_ids = validate_knockout_requirement_ids(requirements, knockout_ids)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"unable to load --knockouts: {exc}") from exc

    _validate_procurement_outputs(args)

    if args.command == "rank":
        if len(args.vendors) < 2:
            raise SystemExit("rank requires at least two vendor inputs")
        if _ifc_options_supplied(args) and not any(
            _vendor_has_evidence_suffix(vendor, ".ifc") for vendor in args.vendors
        ):
            raise SystemExit("IFC selection options require at least one .ifc vendor input or package evidence file")
        if _xlsx_options_supplied(args) and not any(
            _vendor_has_evidence_suffix(vendor, ".xlsx") for vendor in args.vendors
        ):
            raise SystemExit("--xlsx-sheet requires at least one .xlsx vendor input or package evidence file")
        reports = []
        for vendor in args.vendors:
            try:
                facts = _parse_cli_vendor(vendor, args, mixed_rank=True, aliases=aliases)
            except (OSError, RuntimeError, ValueError) as exc:
                raise SystemExit(f"unable to parse vendor input {vendor}: {exc}") from exc
            report = compare(
                requirements,
                facts,
                Path(args.specification).name,
                Path(vendor).name,
                threshold=args.threshold,
                aliases=aliases,
            )
            if knockout_ids is not None:
                apply_knockouts(report, knockout_ids)
            reports.append(report)

        ranked = rank_reports(reports)
        payload = portfolio_to_json(reports)
        if args.output:
            _write_portfolio(reports, args.output)
        if args.clarifications_output:
            write_clarification_portfolio(reports, args.clarifications_output)
        if args.deviations_output:
            write_procurement_review_portfolio(reports, args.deviations_output)
        if args.procurement_output:
            write_procurement_portfolio(reports, args.procurement_output)
        if args.json:
            print(payload)
        else:
            print("BIDLINT — VENDOR RANKING")
            print("=" * 32)
            shown = ranked[: args.top] if args.top else ranked
            for index, report in enumerate(shown, start=1):
                c = report.counts
                gate = f"  GATE {report.knockout.status.value}" if report.knockout is not None else ""
                print(
                    f"{index:>2}. {report.vendor:<30} {report.compliance_score:>5.1f}%  "
                    f"PASS {c['PASS']}  DEV {c['DEVIATION']}  MISS {c['MISSING']}  REVIEW {c['REVIEW']}"
                    f"{gate}"
                )
            if len(shown) < len(ranked):
                remaining = len(ranked) - len(shown)
                print(f"... {remaining} more vendor(s); exports remain complete.")
        return 0

    _validate_scorecard_options(args)
    try:
        facts = _parse_cli_vendor(args.vendor, args, aliases=aliases)
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
    if knockout_ids is not None:
        apply_knockouts(report, knockout_ids)

    if args.output:
        _write_report(report, args.output)
    if args.clarifications_output:
        write_clarification_register(report, args.clarifications_output)
    if args.deviations_output:
        write_procurement_review_register(report, args.deviations_output)
    if args.procurement_output:
        write_procurement_readiness(report, args.procurement_output)
    if args.scorecard_output:
        try:
            if args.scorecard_contract == "2":
                write_supplier_scorecard_signal_v2(report, args.supplier_name, args.scorecard_output)
            else:
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
            print(
                f"{finding.status.value:10} {finding.requirement.id}  "
                f"{finding.requirement.parameter} — {finding.reason}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
