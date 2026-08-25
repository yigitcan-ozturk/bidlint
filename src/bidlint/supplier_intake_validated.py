from __future__ import annotations

from pathlib import Path

from .supplier_intake import supplier_intake_html_from_register

_ACTIONS_ANCHOR = """<div class=\"actions\">\n  <button class=\"primary\" type=\"button\" onclick=\"downloadResponse()\">Download response JSON</button>"""

_ACTIONS_REPLACEMENT = """<div id=\"readiness-status\" class=\"readiness\" hidden></div>\n<div class=\"actions\">\n  <button class=\"secondary\" type=\"button\" onclick=\"checkResponse()\">Check response</button>\n  <button class=\"primary\" type=\"button\" onclick=\"downloadResponse()\">Download response JSON</button>"""

_DOWNLOAD_ANCHOR = """function downloadResponse() {\n  const payload = collectResponse();\n  const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], {type: 'application/json'});"""

_DOWNLOAD_REPLACEMENT = """function validateResponse(payload) {\n  const errors = [];\n  if (!payload.responder.name) {\n    errors.push('Responder name is required.');\n  }\n  if (!payload.responder.company) {\n    errors.push('Responder company is required.');\n  }\n  payload.responses.forEach((response) => {\n    if (!response.supplier_response && !response.offered_value) {\n      errors.push(`${response.requirement_id}: technical response or offered value is required.`);\n    }\n  });\n  return errors;\n}\nfunction showReadiness(errors) {\n  const status = document.getElementById('readiness-status');\n  status.hidden = false;\n  if (errors.length) {\n    status.className = 'readiness error';\n    status.textContent = errors.join(' ');\n  } else {\n    status.className = 'readiness ready';\n    status.textContent = 'Response is complete enough to download. Evidence adequacy remains subject to buyer review.';\n  }\n}\nfunction checkResponse() {\n  const errors = validateResponse(collectResponse());\n  showReadiness(errors);\n}\nfunction downloadResponse() {\n  const payload = collectResponse();\n  const errors = validateResponse(payload);\n  showReadiness(errors);\n  if (errors.length) {\n    document.getElementById('readiness-status').scrollIntoView({behavior: 'smooth', block: 'center'});\n    return;\n  }\n  const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], {type: 'application/json'});"""

_STYLE_ANCHOR = """small { color: #667085; }"""
_STYLE_REPLACEMENT = """small { color: #667085; }\n.readiness { background: #eef6ff; border: 1px solid #c9e2ff; border-radius: 10px; padding: 12px 14px; margin: 16px 0 0; font-weight: 650; }\n.readiness.error { background: #fff1f0; border-color: #ffc9c2; color: #8a1f11; }\n.readiness.ready { background: #eefaf1; border-color: #bfe5c8; color: #245b31; }"""


def validated_supplier_intake_html_from_register(register: dict) -> str:
    rendered = supplier_intake_html_from_register(register)
    replacements = (
        (_ACTIONS_ANCHOR, _ACTIONS_REPLACEMENT, "actions"),
        (_DOWNLOAD_ANCHOR, _DOWNLOAD_REPLACEMENT, "download function"),
        (_STYLE_ANCHOR, _STYLE_REPLACEMENT, "style"),
    )
    for anchor, replacement, label in replacements:
        if anchor not in rendered:
            raise ValueError(f"supplier intake validation layer could not find {label} anchor")
        rendered = rendered.replace(anchor, replacement, 1)
    return rendered


def write_validated_supplier_intake_from_register(register: dict, path: str | Path) -> None:
    Path(path).write_text(validated_supplier_intake_html_from_register(register), encoding="utf-8")
