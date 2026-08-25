from __future__ import annotations

import html
import json
from pathlib import Path

from . import __version__
from .clarifications import clarification_register
from .models import ComplianceReport

_RESPONSE_CONTRACT = "bidlint.supplier-clarification-response"
_RESPONSE_CONTRACT_VERSION = "1"


def _json_for_script(value: object) -> str:
    """Serialize JSON safely for embedding inside an HTML script block."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _source_label(source: dict | None) -> str:
    if not source:
        return "Not available"
    parts = [source.get("document")]
    if source.get("page") is not None:
        parts.append(f"page {source['page']}")
    if source.get("section"):
        parts.append(f"section {source['section']}")
    return ", ".join(str(part) for part in parts if part)


def _evidence_label(evidence: dict | None) -> str:
    if not evidence:
        return "No matching vendor evidence was found."
    raw_value = evidence.get("raw_value") or evidence.get("value")
    source = _source_label(evidence.get("source"))
    return f"{evidence.get('parameter')}: {raw_value} — {source}"


def supplier_intake_html(report: ComplianceReport) -> str:
    register = clarification_register(report)
    items = register["bidder_clarifications"] + register["unanswered_requirements"]
    metadata = {
        "contract": _RESPONSE_CONTRACT,
        "contract_version": _RESPONSE_CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "source_register_contract": register["contract"],
        "source_register_contract_version": register["contract_version"],
        "specification": register["specification"],
        "vendor": register["vendor"],
    }

    cards: list[str] = []
    for index, item in enumerate(items, start=1):
        requirement_id = html.escape(str(item["requirement_id"]), quote=True)
        parameter = html.escape(str(item["parameter"]), quote=True)
        category = html.escape(str(item["category"]), quote=True)
        finding_status = html.escape(str(item["finding_status"]), quote=True)
        requirement_text = html.escape(str(item["requirement_text"]), quote=True)
        question = html.escape(str(item["question"]), quote=True)
        spec_source = html.escape(_source_label(item.get("specification_source")), quote=True)
        vendor_evidence = html.escape(_evidence_label(item.get("vendor_evidence")), quote=True)
        cards.append(
            f"""
            <section class="item" data-index="{index - 1}" data-requirement-id="{requirement_id}"
                     data-parameter="{parameter}" data-category="{category}" data-finding-status="{finding_status}">
              <div class="item-head">
                <div><span class="pill">{finding_status}</span> <strong>{requirement_id}</strong> — {parameter}</div>
                <div class="category">{category}</div>
              </div>
              <p><strong>Requirement</strong><br>{requirement_text}</p>
              <p><strong>Specification source</strong><br>{spec_source}</p>
              <p><strong>Current vendor evidence</strong><br>{vendor_evidence}</p>
              <p class="question"><strong>Clarification requested</strong><br>{question}</p>
              <label>Supplier response
                <textarea class="supplier-response" rows="5" placeholder="State the technical response clearly. Do not include confidential information unless your normal project controls allow it."></textarea>
              </label>
              <div class="grid">
                <label>Offered / confirmed value
                  <input class="offered-value" type="text" placeholder="e.g. 95">
                </label>
                <label>Unit / designation
                  <input class="offered-unit" type="text" placeholder="e.g. mm, MPa, ASTM A182 F317L">
                </label>
              </div>
              <label>Evidence reference
                <input class="evidence-reference" type="text" placeholder="Document, drawing, certificate, page/section, test report reference">
              </label>
              <label>Comments / deviation note
                <textarea class="supplier-comment" rows="3" placeholder="Optional qualification, exception or note"></textarea>
              </label>
            </section>
            """
        )

    empty_state = ""
    if not items:
        empty_state = (
            '<section class="empty"><strong>No supplier clarification is currently required.</strong>'
            "<p>The comparison contains no REVIEW or MISSING findings.</p></section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BidLint Supplier Clarification — {html.escape(report.vendor)}</title>
<style>
:root {{ font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f4f6f8; }}
body {{ margin: 0; }}
main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 56px; }}
header, .item, .empty {{ background: white; border: 1px solid #dfe3e8; border-radius: 14px; padding: 22px; margin-bottom: 18px; }}
h1 {{ margin: 0 0 8px; font-size: 28px; }}
.meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-top: 18px; }}
.notice {{ background: #eef6ff; border: 1px solid #c9e2ff; border-radius: 10px; padding: 12px 14px; margin-top: 18px; }}
.item-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
.pill {{ display: inline-block; font-size: 12px; font-weight: 700; padding: 4px 8px; border-radius: 999px; background: #fff4cc; }}
.category {{ font-size: 12px; color: #667085; }}
.question {{ background: #fff8e6; border-left: 4px solid #e4a11b; padding: 10px 12px; }}
label {{ display: block; font-weight: 650; margin-top: 14px; }}
input, textarea {{ box-sizing: border-box; width: 100%; margin-top: 7px; padding: 10px 11px; border: 1px solid #cfd5dd; border-radius: 8px; font: inherit; font-weight: 400; background: #fff; }}
textarea {{ resize: vertical; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.actions {{ position: sticky; bottom: 0; background: rgba(244,246,248,.96); backdrop-filter: blur(8px); padding: 14px 0; display: flex; gap: 10px; flex-wrap: wrap; }}
button {{ border: 0; border-radius: 9px; padding: 11px 16px; font: inherit; font-weight: 700; cursor: pointer; }}
.primary {{ background: #172033; color: white; }}
.secondary {{ background: white; color: #172033; border: 1px solid #cfd5dd; }}
small {{ color: #667085; }}
@media (max-width: 680px) {{ .grid {{ grid-template-columns: 1fr; }} .item-head {{ flex-direction: column; }} }}
@media print {{ .actions, .notice {{ display: none; }} body {{ background: white; }} main {{ max-width: none; padding: 0; }} .item, header {{ break-inside: avoid; }} }}
</style>
</head>
<body>
<main>
<header>
  <h1>BidLint Supplier Clarification</h1>
  <p>Offline response form generated from deterministic BidLint findings.</p>
  <div class="meta">
    <div><small>Specification</small><br><strong>{html.escape(report.specification)}</strong></div>
    <div><small>Vendor</small><br><strong>{html.escape(report.vendor)}</strong></div>
    <div><small>Open items</small><br><strong>{len(items)}</strong></div>
  </div>
  <div class="notice"><strong>Privacy:</strong> this file makes no network requests and does not upload responses anywhere. Complete it locally, then use <em>Download response JSON</em> and return that file through your normal approved channel.</div>
  <div class="grid">
    <label>Responder name<input id="responder-name" type="text"></label>
    <label>Company<input id="responder-company" type="text"></label>
  </div>
</header>
{''.join(cards)}
{empty_state}
<div class="actions">
  <button class="primary" type="button" onclick="downloadResponse()">Download response JSON</button>
  <button class="secondary" type="button" onclick="window.print()">Print / Save PDF</button>
</div>
</main>
<script>
const metadata = {_json_for_script(metadata)};
function valueOf(item, selector) {{
  const node = item.querySelector(selector);
  return node ? node.value.trim() : "";
}}
function collectResponse() {{
  const responses = Array.from(document.querySelectorAll('.item')).map((item) => ({{
    category: item.dataset.category,
    requirement_id: item.dataset.requirementId,
    parameter: item.dataset.parameter,
    finding_status: item.dataset.findingStatus,
    supplier_response: valueOf(item, '.supplier-response'),
    offered_value: valueOf(item, '.offered-value'),
    offered_unit_or_designation: valueOf(item, '.offered-unit'),
    evidence_reference: valueOf(item, '.evidence-reference'),
    supplier_comment: valueOf(item, '.supplier-comment')
  }}));
  return {{
    ...metadata,
    responder: {{
      name: document.getElementById('responder-name').value.trim(),
      company: document.getElementById('responder-company').value.trim()
    }},
    response_count: responses.length,
    responses
  }};
}}
function downloadResponse() {{
  const payload = collectResponse();
  const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], {{type: 'application/json'}});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'bidlint-supplier-response.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>
"""


def write_supplier_intake(report: ComplianceReport, path: str | Path) -> None:
    Path(path).write_text(supplier_intake_html(report), encoding="utf-8")
