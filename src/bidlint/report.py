from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from .models import ComplianceReport


def to_json(report: ComplianceReport) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def portfolio_to_json(reports: list[ComplianceReport]) -> str:
    ranked = sorted(
        reports,
        key=lambda r: (
            -r.compliance_score,
            r.counts["DEVIATION"] + r.counts["MISSING"],
            r.vendor.lower(),
        ),
    )
    return json.dumps(
        {
            "tool": "bidlint",
            "version": "0.1.0",
            "ranking": [
                {
                    "rank": index,
                    "vendor": report.vendor,
                    "compliance_score": report.compliance_score,
                    "counts": report.counts,
                }
                for index, report in enumerate(ranked, start=1)
            ],
            "reports": [report.to_dict() for report in ranked],
        },
        indent=2,
        ensure_ascii=False,
    )


def to_markdown(report: ComplianceReport) -> str:
    c = report.counts
    lines = [
        "# bidlint technical compliance report",
        "",
        f"- **Specification:** {report.specification}",
        f"- **Vendor:** {report.vendor}",
        f"- **Compliance score:** {report.compliance_score:.1f}%",
        f"- **PASS:** {c['PASS']} · **DEVIATION:** {c['DEVIATION']} · **MISSING:** {c['MISSING']} · **REVIEW:** {c['REVIEW']}",
        "",
        "| Status | Requirement | Required | Offered | Confidence | Source |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for finding in report.findings:
        req = finding.requirement
        fact = finding.vendor_fact
        required = f"{req.operator or ''} {req.value:g}{req.unit or ''}" if req.value is not None else "qualitative"
        offered = fact.raw_value if fact else "—"
        src = f"p.{req.source.page}" if req.source and req.source.page else "—"
        lines.append(
            f"| {finding.status.value} | {req.parameter} | {required} | {offered} | {finding.confidence:.2f} | {src} |"
        )
    lines.extend(["", "## Findings", ""])
    for finding in report.findings:
        req = finding.requirement
        fact = finding.vendor_fact
        lines.append(f"### {finding.status.value} — {req.id} — {req.parameter}")
        lines.append("")
        lines.append(f"**Requirement:** {req.text}")
        if fact:
            lines.append(f"**Offered:** {fact.parameter}: {fact.raw_value}")
        lines.append(f"**Reason:** {finding.reason}")
        lines.append("")
    return "\n".join(lines)


def to_html(report: ComplianceReport) -> str:
    c = report.counts
    rows: list[str] = []
    for finding in report.findings:
        req = finding.requirement
        fact = finding.vendor_fact
        required = f"{req.operator or ''} {req.value:g}{req.unit or ''}" if req.value is not None else "qualitative"
        offered = fact.raw_value if fact else "—"
        spec_page = f"p.{req.source.page}" if req.source and req.source.page else "—"
        vendor_page = f"p.{fact.source.page}" if fact and fact.source and fact.source.page else "—"
        rows.append(
            "<tr>"
            f'<td><span class="status {finding.status.value.lower()}">{html.escape(finding.status.value)}</span></td>'
            f"<td><strong>{html.escape(req.parameter)}</strong><div class=muted>{html.escape(req.text)}</div></td>"
            f"<td>{html.escape(required)}</td>"
            f"<td>{html.escape(offered)}</td>"
            f"<td>{finding.confidence:.2f}</td>"
            f"<td>{html.escape(spec_page)} / {html.escape(vendor_page)}</td>"
            f"<td>{html.escape(finding.reason)}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bidlint — {html.escape(report.vendor)}</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f6f7f9; color: #16181d; }}
main {{ width: min(1180px, calc(100% - 40px)); margin: 40px auto 72px; }}
.hero {{ background: #111318; color: white; border-radius: 22px; padding: 30px; box-shadow: 0 16px 50px rgba(0,0,0,.12); }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .14em; font-size: 12px; opacity: .62; }}
h1 {{ margin: 8px 0 10px; font-size: clamp(28px, 5vw, 54px); line-height: 1; }}
.subtitle {{ color: #b9bec9; max-width: 780px; }}
.score-grid {{ display: grid; grid-template-columns: 1.5fr repeat(4, 1fr); gap: 10px; margin-top: 24px; }}
.metric {{ background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.08); padding: 16px; border-radius: 14px; }}
.metric strong {{ display: block; font-size: 28px; }}
.metric span {{ font-size: 12px; color: #b9bec9; text-transform: uppercase; letter-spacing: .08em; }}
.panel {{ background: white; margin-top: 20px; border-radius: 18px; overflow: hidden; border: 1px solid #e7e9ee; }}
.panel-head {{ padding: 20px 22px; border-bottom: 1px solid #eceef2; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ text-align: left; vertical-align: top; padding: 14px 12px; border-bottom: 1px solid #eef0f3; }}
th {{ background: #fafbfc; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: #626873; }}
.status {{ display: inline-block; min-width: 82px; text-align: center; border-radius: 999px; padding: 5px 8px; font-weight: 750; font-size: 11px; }}
.pass {{ background: #e9f8ef; color: #176a3a; }}
.deviation {{ background: #fdecec; color: #a62222; }}
.missing {{ background: #fff4da; color: #875f00; }}
.review {{ background: #edf0ff; color: #3849a5; }}
.muted {{ color: #777e89; font-size: 12px; margin-top: 5px; max-width: 520px; }}
footer {{ color: #767d88; font-size: 12px; padding: 18px 4px; }}
@media (max-width: 900px) {{ .score-grid {{ grid-template-columns: repeat(2, 1fr); }} .score-grid .metric:first-child {{ grid-column: 1 / -1; }} .panel {{ overflow-x: auto; }} table {{ min-width: 980px; }} }}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div class="eyebrow">bidlint technical compliance</div>
    <h1>{report.compliance_score:.1f}%</h1>
    <div class="subtitle">{html.escape(report.specification)} → {html.escape(report.vendor)}</div>
    <div class="score-grid">
      <div class="metric"><strong>{report.compliance_score:.1f}%</strong><span>Compliance score</span></div>
      <div class="metric"><strong>{c['PASS']}</strong><span>Pass</span></div>
      <div class="metric"><strong>{c['DEVIATION']}</strong><span>Deviation</span></div>
      <div class="metric"><strong>{c['MISSING']}</strong><span>Missing</span></div>
      <div class="metric"><strong>{c['REVIEW']}</strong><span>Review</span></div>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head"><strong>Compliance matrix</strong><div class="muted">Every finding retains specification and vendor source-page provenance.</div></div>
    <table>
      <thead><tr><th>Status</th><th>Requirement</th><th>Required</th><th>Offered</th><th>Match</th><th>Sources</th><th>Reason</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
  <footer>Generated locally by bidlint v0.1.0. No external AI API is required.</footer>
</main>
</body>
</html>"""


def write_csv(report: ComplianceReport, path: str | Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
        for finding in report.findings:
            req = finding.requirement
            fact = finding.vendor_fact
            writer.writerow(
                {
                    "status": finding.status.value,
                    "requirement_id": req.id,
                    "parameter": req.parameter,
                    "required": req.text,
                    "offered": fact.raw_value if fact else "",
                    "confidence": finding.confidence,
                    "spec_page": req.source.page if req.source else "",
                    "vendor_page": fact.source.page if fact and fact.source else "",
                    "reason": finding.reason,
                }
            )
