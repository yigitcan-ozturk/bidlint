from __future__ import annotations

import zipfile

from bidlint.sanitize_scan import scan_file


def _xlsx(path, *, cell_text: str | None = None) -> None:
    shared = ""
    worksheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData/></worksheet>"
    )
    if cell_text is not None:
        shared = (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
            f"<si><t>{cell_text}</t></si></sst>"
        )
        worksheet = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>'
        )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"></workbook>',
        )
        archive.writestr(
            "xl/styles.xml",
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<cellXfs count="1"><xf numFmtId="0"/></cellXfs></styleSheet>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
        if shared:
            archive.writestr("xl/sharedStrings.xml", shared)


def test_standard_ooxml_namespace_urls_do_not_create_review_noise(tmp_path):
    workbook = tmp_path / "sanitized.xlsx"
    _xlsx(workbook)

    findings = scan_file(workbook)

    assert not any(finding.category == "url" for finding in findings)


def test_real_url_in_ooxml_cell_content_still_requires_review(tmp_path):
    workbook = tmp_path / "sanitized.xlsx"
    _xlsx(workbook, cell_text="Public reference https://example.com/drainage")

    findings = scan_file(workbook)

    url_findings = [finding for finding in findings if finding.category == "url"]
    assert len(url_findings) == 1
    assert url_findings[0].severity == "REVIEW"
    assert url_findings[0].location == "xl/sharedStrings.xml"
