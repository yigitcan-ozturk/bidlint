import csv

import pytest

from bidlint.cli import _write_portfolio, build_parser
from bidlint.compare import compare
from bidlint.models import Requirement, SourceRef, VendorFact
from bidlint.portfolio import portfolio_to_html, portfolio_to_markdown, rank_reports, write_portfolio_csv


def req(identifier, parameter, operator, value, unit=None):
    return Requirement(
        identifier,
        f"{parameter} {operator} {value}",
        parameter,
        operator,
        value,
        unit,
        True,
        SourceRef("spec.pdf", 1),
    )


def fact(parameter, value, unit=None):
    return VendorFact(parameter, f"{value}{unit or ''}", value, unit, SourceRef("vendor.pdf", 1))


def portfolio_reports():
    requirements = [
        req("R0001", "motor efficiency", ">=", 90, "%"),
        req("R0002", "ip rating", ">=", 65),
    ]
    vendor_a = compare(
        requirements,
        [fact("motor efficiency", 93, "%"), fact("ip rating", 65)],
        "spec.pdf",
        "vendor-a.pdf",
    )
    vendor_b = compare(
        requirements,
        [fact("motor efficiency", 88, "%"), fact("ip rating", 65)],
        "spec.pdf",
        "vendor-b.pdf",
    )
    return vendor_a, vendor_b


def test_rank_reports_is_deterministic():
    vendor_a, vendor_b = portfolio_reports()
    ranked = rank_reports([vendor_b, vendor_a])
    assert [report.vendor for report in ranked] == ["vendor-a.pdf", "vendor-b.pdf"]


def test_portfolio_html_contains_ranking_and_requirement_matrix():
    vendor_a, vendor_b = portfolio_reports()
    rendered = portfolio_to_html([vendor_b, vendor_a])
    assert "Technical bid tabulation" in rendered
    assert "Requirement-by-vendor matrix" in rendered
    assert "vendor-a.pdf" in rendered
    assert "vendor-b.pdf" in rendered
    assert "R0001" in rendered
    assert "motor efficiency" in rendered
    assert "DEVIATION" in rendered


def test_portfolio_markdown_contains_ranking_matrix_and_reasons():
    vendor_a, vendor_b = portfolio_reports()
    rendered = portfolio_to_markdown([vendor_b, vendor_a])
    assert "# bidlint technical bid tabulation" in rendered
    assert "## Vendor ranking" in rendered
    assert "## Requirement-by-vendor matrix" in rendered
    assert rendered.index("vendor-a.pdf") < rendered.index("vendor-b.pdf")
    assert "**DEVIATION**" in rendered
    assert "does not satisfy" in rendered


def test_portfolio_markdown_output_suffix_is_supported(tmp_path):
    vendor_a, vendor_b = portfolio_reports()
    output = tmp_path / "ranking.md"
    _write_portfolio([vendor_b, vendor_a], str(output))
    rendered = output.read_text(encoding="utf-8")
    assert "Technical bid" in rendered or "technical bid" in rendered
    assert "vendor-a.pdf" in rendered


def test_portfolio_csv_is_long_form_and_ranked(tmp_path):
    vendor_a, vendor_b = portfolio_reports()
    output = tmp_path / "ranking.csv"
    write_portfolio_csv([vendor_b, vendor_a], output)

    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 4
    assert rows[0]["rank"] == "1"
    assert rows[0]["vendor"] == "vendor-a.pdf"
    assert {row["requirement_id"] for row in rows} == {"R0001", "R0002"}
    assert any(row["vendor"] == "vendor-b.pdf" and row["status"] == "DEVIATION" for row in rows)


def test_rank_cli_accepts_positive_top_n_and_rejects_zero():
    parser = build_parser()
    args = parser.parse_args(["rank", "spec.pdf", "a.pdf", "b.pdf", "--top", "1"])
    assert args.top == 1

    with pytest.raises(SystemExit):
        parser.parse_args(["rank", "spec.pdf", "a.pdf", "b.pdf", "--top", "0"])


def test_portfolio_exports_reject_empty_report_sets(tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        portfolio_to_html([])
    with pytest.raises(ValueError, match="at least one"):
        portfolio_to_markdown([])
    with pytest.raises(ValueError, match="at least one"):
        write_portfolio_csv([], tmp_path / "empty.csv")
