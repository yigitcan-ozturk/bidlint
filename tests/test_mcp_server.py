from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.mcp_server import compare_documents, explain_requirement, extract_document


def make_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 22
    c.save()


def test_mcp_extract_compare_and_explain_use_deterministic_core(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    specification = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11000 W"])

    extracted = extract_document("spec.pdf", "specification")
    assert extracted["count"] == 1
    assert extracted["items"][0]["parameter"] == "motor power"
    assert extracted["items"][0]["source"]["page"] == 1

    report = compare_documents("spec.pdf", "vendor.pdf")
    assert report["compliance_score"] == 100.0
    assert report["findings"][0]["status"] == "PASS"

    explanation = explain_requirement("spec.pdf", "vendor.pdf", "R0001")
    finding = explanation["finding"]
    assert finding["status"] == "PASS"
    assert "satisfies" in finding["reason"]
    assert finding["requirement"]["source"]["document"] == "spec.pdf"
    assert finding["vendor_fact"]["source"]["document"] == "vendor.pdf"


def test_mcp_root_blocks_parent_traversal_and_absolute_escape(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.pdf"
    make_pdf(outside, ["Motor power: 11 kW"])
    monkeypatch.setenv("BIDLINT_MCP_ROOT", str(root))

    with pytest.raises(ValueError, match="within MCP root"):
        extract_document("../outside.pdf", "vendor")
    with pytest.raises(ValueError, match="within MCP root"):
        extract_document(str(outside), "vendor")


def test_mcp_root_rejects_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.pdf"
    make_pdf(outside, ["Motor power: 11 kW"])
    link = root / "linked.pdf"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available on this platform")
    monkeypatch.setenv("BIDLINT_MCP_ROOT", str(root))

    with pytest.raises(ValueError, match="within MCP root"):
        extract_document("linked.pdf", "vendor")


def test_mcp_rejects_wrong_suffix_missing_files_and_invalid_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    text_file = tmp_path / "notes.txt"
    text_file.write_text("not a pdf", encoding="utf-8")
    specification = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11 kW"])

    with pytest.raises(ValueError, match="expected a .pdf"):
        extract_document("notes.txt", "vendor")
    with pytest.raises(ValueError, match="does not exist"):
        extract_document("missing.pdf", "vendor")
    with pytest.raises(ValueError, match="threshold"):
        compare_documents("spec.pdf", "vendor.pdf", threshold=1.1)


def test_mcp_explain_rejects_unknown_requirement(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    specification = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11 kW"])

    with pytest.raises(ValueError, match="requirement not found"):
        explain_requirement("spec.pdf", "vendor.pdf", "R9999")
