from __future__ import annotations

import csv
import html
from pathlib import Path

from . import __version__
from .models import ComplianceReport


def rank_reports(reports: list[ComplianceReport]) -> list[ComplianceReport]:
    """Rank reports with a deterministic, documented tie-break order."""
    return sorted(
        reports,
        key=lambda report: (
            -report.compliance_score,
            report.counts["DEVIATION"] + report.counts["MISSING"],
            report.counts["REVIEW"],
            report.vendor.lower(),
        ),
    )


def _required_text(report: ComplianceReport, requirement_id: str) -> str:
    for finding in report.findings:
        req = finding.requirement
        if req.id == requirement_id:
            if req.value is None:
                return "qualitative"
            return f"{req.operator or ''} {req.value:g}{req.unit or ''}".strip()
    return "—"


def portfolio_to_html(reports: list[ComplianceReport]) -> str:
    ranked = rank_reports(reports)
    if not ranked:
        raise ValueError("portfolio report requires at least one vendor report")

    specification = ranked[0].specification
    summary_rows: list[str] = []
    for index, report in enumerate(ranked, start=1):
        counts = report.counts
        summary_rows.append(
            "<tr>"
            f"<td class=rank>{index}</td>"
            f"<td><strong>{html.escape(report.vendor)}</strong></td>"
            f"<td><strong>{report.compliance_score:.1f}%</strong></td>"
            f"<td>{counts['PASS']}</td>"
            f"<td>{counts['DEVIATION']}</td>"
            f"<td>{counts['MISSING']}</td>"
            f"<td>{counts['REVIEW']}</td>"
            "</tr>"
        )

    requirement_ids: list[str] = []
    requirement_labels: dict[str, str] = {}
    for report in ranked:
        for finding in report.findings:
            req = finding.requirement
            if req.id not in requirement_labels:
                requirement_ids.append(req.id)
                requirement_labels[req.id] = req.parameter

    vendor_maps = [
        {finding.requirement.id: finding for finding in report.findings}
        for report in ranked
    ]
    matrix_rows: list[str] = []
    for requirement_id in requirement_ids:
        required = _required_text(ranked[0], requirement_id)
        cells = []
        for report, finding_map in zip(ranked, vendor_maps, strict=True):
            finding = finding_map.get(requirement_id)
            if finding is None:
                cells.append('<td><span class="status missing">MISSING</span><div class=muted>No finding</div></td>')
                continue
            fact = finding.vendor_fact
            offered = fact.raw_value if fact else "—"
            cells.append(
                "<td>"
                f'<span class="status {finding.status.value.lower()}">{html.escape(finding.status.value)}</span>'
                f"<div class=offered>{html.escape(offered)}</div>"
                f"<div class=muted>{html.escape(finding.reason)}</div>"
                "</td>"
            )
        matrix_rows.append(
            "<tr>"
            f"<td><strong>{html.escape(requirement_id)}</strong><div>{html.escape(requirement_labels[requirement_id])}</div>"
            f"<div class=muted>{html.escape(required)}</div></td>"
            f"{''.join(cells)}"
            "</tr>"
        )

    vendor_headers = "".join(f"<th>{html.escape(report.vendor)}</th>" for report in ranked)
    vendor_count = len(ranked)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bidlint — technical bid tabulation</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f6f7f9; color: #16181d; }}
main {{ width: min(1380px, calc(100% - 40px)); margin: 40px auto 72px; }}
.hero {{ background: #111318; color: white; border-radius: 22px; padding: 32px; box-shadow: 0 16px 50px rgba(0,0,0,.12); }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .14em; font-size: 12px; color: #aeb4c0; }}
h1 {{ margin: 8px 0 12px; font-size: clamp(30px, 5vw, 52px); line-height: 1.02; }}
.subtitle {{ color: #b9bec9; max-width: 860px; }}
.hero-grid {{ display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; }}
.hero-stat {{ background: rgba(255,255,255,.08); padding: 14px 18px; border-radius: 14px; min-width: 150px; }}
.hero-stat strong {{ display: block; font-size: 24px; }}
.hero-stat span {{ color: #b9bec9; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
.panel {{ background: white; margin-top: 20px; border-radius: 18px; overflow: hidden; border: 1px solid #e7e9ee; }}
.panel-head {{ padding: 20px 22px; border-bottom: 1px solid #eceef2; }}
.panel-body {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ text-align: left; vertical-align: top; padding: 14px 12px; border-bottom: 1px solid #eef0f3; }}
th {{ background: #fafbfc; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: #626873; }}
.rank {{ font-size: 18px; font-weight: 800; width: 54px; }}
.status {{ display: inline-block; min-width: 82px; text-align: center; border-radius: 999px; padding: 5px 8px; font-weight: 750; font-size: 11px; }}
.pass {{ background: #e9f8ef; color: #176a3a; }}
.deviation {{ background: #fdecec; color: #a62222; }}
.missing {{ background: #fff4da; color: #875f00; }}
.review {{ background: #edf0ff; color: #3849a5; }}
.offered {{ margin-top: 8px; font-weight: 650; }}
.muted {{ color: #777e89; font-size: 11px; margin-top: 5px; max-width: 360px; }}
.matrix {{ min-width: max(980px, calc(260px + {vendor_count} * 230px)); }}
footer {{ color: #767d88; font-size: 12px; padding: 18px 4px; }}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div class="eyebrow">bidlint multi-vendor technical compliance</div>
    <h1>Technical bid tabulation</h1>
    <div class="subtitle">{html.escape(specification)} · deterministic ranking with evidence-preserving requirement comparisons</div>
    <div class="hero-grid">
      <div class="hero-stat"><strong>{vendor_count}</strong><span>Vendors</span></div>
      <div class="hero-stat"><strong>{len(requirement_ids)}</strong><span>Requirements</span></div>
      <div class="hero-stat"><strong>{ranked[0].compliance_score:.1f}%</strong><span>Top score</span></div>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head"><strong>Vendor ranking</strong><div class=muted>Higher compliance first; ties prefer fewer deviations/missing findings, then fewer reviews, then vendor name.</div></div>
    <div class="panel-body">
      <table>
        <thead><tr><th>Rank</th><th>Vendor</th><th>Score</th><th>Pass</th><th>Deviation</th><th>Missing</th><th>Review</th></tr></thead>
        <tbody>{''.join(summary_rows)}</tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head"><strong>Requirement-by-vendor matrix</strong><div class=muted>Each cell shows the status, offered value and deterministic reason.</div></div>
    <div class="panel-body">
      <table class="matrix">
        <thead><tr><th>Requirement</th>{vendor_headers}</tr></thead>
        <tbody>{''.join(matrix_rows)}</tbody>
      </table>
    </div>
  </section>

  <footer>Generated locally by bidlint v{__version__}. No external AI API is required.</footer>
</main>
</body>
</html>"""


def write_portfolio_csv(reports: list[ComplianceReport], path: str | Path) -> None:
    ranked = rank_reports(reports)
    if not ranked:
        raise ValueError("portfolio report requires at least one vendor report")

    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rank",
                "vendor",
                "compliance_score",
                "status",
                "requirement_id",
                "parameter",
                "required",
                "offered",
                "confidence",
                "spec_page",
                "vendor_page",
                "reason",
            ],
        )
        writer.writeheader()
        for rank, report in enumerate(ranked, start=1):
            for finding in report.findings:
                req = finding.requirement
                fact = finding.vendor_fact
                required = (
                    f"{req.operator or ''} {req.value:g}{req.unit or ''}".strip()
                    if req.value is not None
                    else "qualitative"
                )
                writer.writerow(
                    {
                        "rank": rank,
                        "vendor": report.vendor,
                        "compliance_score": report.compliance_score,
                        "status": finding.status.value,
                        "requirement_id": req.id,
                        "parameter": req.parameter,
                        "required": required,
                        "offered": fact.raw_value if fact else "",
                        "confidence": finding.confidence,
                        "spec_page": req.source.page if req.source else "",
                        "vendor_page": fact.source.page if fact and fact.source else "",
                        "reason": finding.reason,
                    }
                )
