from __future__ import annotations

import json
import zipfile
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.errors import ExitCode
from bidlint.pilot import parse_manifest_payload
from bidlint.sanitize_scan import guarded_pilot_main, scan_file, scan_manifest


def _make_pdf(path: Path, lines: list[str], *, author: str | None = None, title: str | None = None) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setSubject("")
    if author is not None:
        pdf.setAuthor(author)
    if title is not None:
        pdf.setTitle(title)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def test_pdf_scan_finds_sensitive_categories_without_echoing_match(tmp_path):
    document = tmp_path / "offer.pdf"
    _make_pdf(
        document,
        [
            "Contact procurement@example.com",
            "Phone +44 7700 900123",
            "Total price EUR 6,240.00 EXW",
            "Example Industrial Limited",
        ],
        author="Private Author",
        title="Customer RFQ",
    )

    findings = scan_file(document)
    categories = {finding.category for finding in findings if finding.severity == "BLOCK"}
    assert "email-address" in categories
    assert "phone-number" in categories
    assert "commercial-money" in categories
    assert "commercial-terms" in categories
    assert "legal-entity-name" in categories
    assert "pdf-metadata" in categories

    rendered = json.dumps([finding.to_dict() for finding in findings])
    assert "procurement@example.com" not in rendered
    assert "6,240.00" not in rendered
    assert "+44 7700 900123" not in rendered
    assert "Private Author" not in rendered


def test_clean_pdf_is_automatically_clear_but_still_requires_visual_review(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 11 kW"])

    manifest = parse_manifest_payload(
        {
            "pilot_id": "sanitized-pump-001",
            "specification": "specification.pdf",
            "vendors": ["vendor.pdf"],
            "repeats": 2,
        },
        base_dir=tmp_path,
    )
    result = scan_manifest(manifest)

    assert result["automated_clear"] is True
    assert result["blocker_count"] == 0
    assert result["manual_review_required"] is True
    assert any(finding["category"] == "pdf-visual-content-uninspected" for finding in result["findings"])


def test_ooxml_scan_blocks_hidden_sheets_comments_and_external_links(tmp_path):
    workbook = tmp_path / "vendor.xlsx"
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook><sheets><sheet name="Private" state="veryHidden"/></sheets></workbook>',
        )
        archive.writestr("xl/comments1.xml", "<comments><t>internal comment</t></comments>")
        archive.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
        archive.writestr("docProps/core.xml", "<coreProperties><creator>Private Author</creator></coreProperties>")

    findings = scan_file(workbook)
    categories = {finding.category for finding in findings if finding.severity == "BLOCK"}
    assert "xlsx-hidden-sheets" in categories
    assert "ooxml-comments" in categories
    assert "xlsx-external-links" in categories
    assert "ooxml-core-metadata" in categories


def test_guarded_pilot_rejects_unsanitized_corpus_before_execution(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    manifest = tmp_path / "pilot.json"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 11 kW", "Contact: secret@example.com"])
    manifest.write_text(
        json.dumps(
            {
                "pilot_id": "external-pilot-001",
                "specification": "specification.pdf",
                "vendors": ["vendor.pdf"],
                "repeats": 2,
            }
        ),
        encoding="utf-8",
    )

    exit_code = guarded_pilot_main([str(manifest), "--json"])

    assert exit_code == int(ExitCode.INPUT)
    captured = capsys.readouterr()
    assert "sanitization scan found" in captured.err
    assert "secret@example.com" not in captured.err
    assert captured.out == ""


def test_manifest_scan_blocks_commercial_terms_in_policy_files(tmp_path):
    specification = tmp_path / "specification.pdf"
    vendor = tmp_path / "vendor.pdf"
    aliases = tmp_path / "aliases.json"
    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor, ["Motor power: 11 kW"])
    aliases.write_text('{"motor power": "unit price EUR 100"}', encoding="utf-8")

    manifest = parse_manifest_payload(
        {
            "pilot_id": "sanitized-pump-002",
            "specification": "specification.pdf",
            "vendors": ["vendor.pdf"],
            "options": {"aliases": "aliases.json"},
        },
        base_dir=tmp_path,
    )
    result = scan_manifest(manifest)

    assert result["automated_clear"] is False
    assert any(
        finding["file"].startswith("aliases/") and finding["category"] == "commercial-money"
        for finding in result["findings"]
    )
