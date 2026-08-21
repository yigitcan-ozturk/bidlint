from __future__ import annotations

import json
import zipfile
from xml.etree import ElementTree as ET

from bidlint.pilot_gate import evaluate_release_gate

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("", _MAIN_NS)
ET.register_namespace("r", _REL_NS)


def _q(tag: str) -> str:
    return f"{{{_MAIN_NS}}}{tag}"


def _rq(tag: str) -> str:
    return f"{{{_REL_NS}}}{tag}"


def _pq(tag: str) -> str:
    return f"{{{_PACKAGE_REL_NS}}}{tag}"


def _xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _write_spec(path) -> None:
    rows = [
        ["Technical schedule"],
        ["General Requirement", "Specification"],
        ["Material", "Grade 304 stainless steel"],
        ["Load Class", "A15"],
        [],
        ["Item", "Length (mm)"],
        [1, 3000],
    ]
    worksheet = ET.Element(_q("worksheet"))
    data = ET.SubElement(worksheet, _q("sheetData"))
    for row_number, values in enumerate(rows, start=1):
        row = ET.SubElement(data, _q("row"), {"r": str(row_number)})
        for column, value in enumerate(values, start=1):
            if value in (None, ""):
                continue
            ref = f"{'AB'[column - 1]}{row_number}"
            if isinstance(value, (int, float)):
                cell = ET.SubElement(row, _q("c"), {"r": ref})
                ET.SubElement(cell, _q("v")).text = str(value)
            else:
                cell = ET.SubElement(row, _q("c"), {"r": ref, "t": "inlineStr"})
                inline = ET.SubElement(cell, _q("is"))
                ET.SubElement(inline, _q("t")).text = str(value)

    workbook = ET.Element(_q("workbook"))
    sheets = ET.SubElement(workbook, _q("sheets"))
    ET.SubElement(sheets, _q("sheet"), {"name": "Schedule", "sheetId": "1", _rq("id"): "rId1"})
    rels = ET.Element(_pq("Relationships"))
    ET.SubElement(
        rels,
        _pq("Relationship"),
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": "/xl/worksheets/sheet1.xml",
        },
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", _xml(worksheet))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(rels))


def _evidence() -> dict:
    return {
        "tool": "bidlint-pilot",
        "pilot_id": "external-pilot-001",
        "mode": "compare",
        "repeats": 2,
        "passed": True,
        "deterministic": True,
        "conformant": True,
        "report_count": 1,
        "output_digest_sha256": "out-aaa",
        "run_digests_sha256": ["out-aaa", "out-aaa"],
        "manifest_digest_sha256": "manifest-aaa",
        "corpus_digest_sha256": "corpus-aaa",
        "corpus": [],
        "conformance_issue_count": 0,
        "conformance_issues": [],
    }


def _review(*, scope_reviewed: bool) -> dict:
    return {
        "tool": "bidlint-pilot-review",
        "pilot_id": "external-pilot-001",
        "sanitization": {
            "approved": True,
            "reviewer": "Sanitization Reviewer",
            "reviewed_at": "2026-08-21",
            "review_findings_resolved": True,
        },
        "technical": {
            "decision": "APPROVE_BASELINE",
            "reviewer": "Domain Reviewer",
            "reviewed_at": "2026-08-21",
            "all_non_pass_findings_reviewed": True,
            "specification_scope_reviewed": scope_reviewed,
            "false_positive_count": 0,
            "false_negative_count": 0,
            "unresolved_limitation_count": 0,
            "known_product_defect_count": 0,
            "regression_fixtures_created": 0,
            "explicit_knockouts_only": True,
            "no_commercial_scoring": True,
        },
    }


def _workspace(tmp_path, *, scope_reviewed: bool):
    root = tmp_path / ("reviewed" if scope_reviewed else "unreviewed")
    spec_dir = root / "sanitized" / "specification"
    vendor_dir = root / "sanitized" / "vendors" / "vendor-01"
    spec_dir.mkdir(parents=True)
    vendor_dir.mkdir(parents=True)
    (root / "evidence").mkdir()
    (root / "review").mkdir()
    _write_spec(spec_dir / "specification.xlsx")
    (vendor_dir / "vendor.pdf").write_bytes(b"placeholder")
    (root / "pilot.json").write_text(
        json.dumps(
            {
                "pilot_id": "external-pilot-001",
                "specification": "sanitized/specification/specification.xlsx",
                "vendors": ["sanitized/vendors/vendor-01/vendor.pdf"],
                "repeats": 2,
            }
        ),
        encoding="utf-8",
    )
    scan = {
        "tool": "bidlint-pilot-scan",
        "pilot_id": "external-pilot-001",
        "automated_clear": True,
        "manual_review_required": True,
        "files_scanned": 3,
        "blocker_count": 0,
        "review_count": 1,
        "findings": [],
        "limitations": [],
    }
    (root / "evidence" / "sanitization-scan.json").write_text(json.dumps(scan), encoding="utf-8")
    (root / "evidence" / "approved-baseline.json").write_text(json.dumps(_evidence()), encoding="utf-8")
    (root / "evidence" / "replay-evidence.json").write_text(json.dumps(_evidence()), encoding="utf-8")
    (root / "review" / "approval.json").write_text(
        json.dumps(_review(scope_reviewed=scope_reviewed)),
        encoding="utf-8",
    )
    return root


def test_release_gate_blocks_unscoped_xlsx_schedule_until_human_scope_review(tmp_path):
    result = evaluate_release_gate(_workspace(tmp_path, scope_reviewed=False))

    assert result["release_ready"] is False
    assert result["specification_coverage"]["manual_scope_review_required"] is True
    assert result["specification_coverage"]["unscoped_populated_row_count"] == 2
    assert "technical.specification_scope_reviewed must be true" in result["failures"]


def test_release_gate_accepts_explicit_scope_review_when_other_evidence_is_ready(tmp_path):
    result = evaluate_release_gate(_workspace(tmp_path, scope_reviewed=True))

    assert result["release_ready"] is True
    assert result["failure_count"] == 0
    assert result["specification_coverage"]["first_unscoped_row"] == 6
