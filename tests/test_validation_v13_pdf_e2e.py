"""End-to-end synthetic PDF evidence probes for the stable BidLint engine.

Generated PDFs are test-only; they are not independent real-world validation.
"""
from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.compare import compare
from bidlint.parse import parse_requirements, parse_vendor_facts
from bidlint.models import Status


def _pdf(path, lines):
    document = canvas.Canvas(str(path), pagesize=A4)
    for index, line in enumerate(lines):
        document.drawString(50, 800 - index * 24, line)
    document.save()


def test_synthetic_pdf_extraction_and_comparison(tmp_path):
    spec = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    _pdf(spec, ["Motor efficiency shall be minimum 90 %", "Noise level must not exceed 70 dB"])
    _pdf(vendor, ["Motor efficiency: 93 %", "Noise level: 75 dB"])

    requirements = parse_requirements(spec)
    facts = parse_vendor_facts(vendor)
    assert len(requirements) == 2
    assert len(facts) == 2

    report = compare(requirements, facts, spec.name, vendor.name)
    assert [finding.status for finding in report.findings] == [Status.PASS, Status.DEVIATION]
    for finding in report.findings:
        assert finding.requirement.source is not None
        assert finding.requirement.source.document == spec.name
        assert finding.requirement.source.page == 1
        assert finding.vendor_fact is not None
        assert finding.vendor_fact.source is not None
        assert finding.vendor_fact.source.document == vendor.name
        assert finding.vendor_fact.source.page == 1


def test_synthetic_pdf_missing_vendor_fact(tmp_path):
    spec = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    _pdf(spec, ["Motor efficiency shall be minimum 90 %"])
    _pdf(vendor, ["Noise level: 60 dB"])

    report = compare(parse_requirements(spec), parse_vendor_facts(vendor), spec.name, vendor.name)
    assert len(report.findings) == 1
    assert report.findings[0].status == Status.MISSING
    assert report.findings[0].vendor_fact is None
