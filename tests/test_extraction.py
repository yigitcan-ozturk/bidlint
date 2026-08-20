from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.compare import compare
from bidlint.extraction import (
    Evidence,
    ExtractionBatch,
    ExtractionKind,
    RequirementCandidate,
    VendorFactCandidate,
    extract_with_provider,
    validate_extraction,
)
from bidlint.models import Status


def make_pdf(path: Path, pages: list[list[str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for page_lines in pages:
        y = 800
        for line in page_lines:
            c.drawString(50, y, line)
            y -= 22
        c.showPage()
    c.save()


def test_requirement_candidate_requires_verifiable_page_evidence(tmp_path):
    path = tmp_path / "spec.pdf"
    make_pdf(path, [["Motor power shall be minimum 10 kW"]])
    batch = ExtractionBatch(
        provider="mock",
        kind=ExtractionKind.SPECIFICATION,
        candidates=[
            RequirementCandidate(
                text="Motor power shall be minimum 10 kW",
                parameter="Motor power",
                operator=">=",
                value=10,
                unit="kW",
                confidence=0.96,
                evidence=Evidence(page=1, text="Motor power shall be minimum 10 kW"),
            )
        ],
    )

    result = validate_extraction(path, batch)
    assert result.accepted_count == 1
    assert result.rejected_count == 0
    requirement = result.items[0]
    assert requirement.id == "R0001"
    assert requirement.parameter == "motor power"
    assert requirement.source.document == "spec.pdf"
    assert requirement.source.page == 1


def test_low_confidence_and_unverifiable_evidence_are_rejected(tmp_path):
    path = tmp_path / "spec.pdf"
    make_pdf(path, [["Design pressure shall be minimum 10 bar"]])
    batch = ExtractionBatch(
        provider="mock",
        kind=ExtractionKind.SPECIFICATION,
        candidates=[
            RequirementCandidate(
                text="Design pressure shall be minimum 10 bar",
                parameter="design pressure",
                operator=">=",
                value=10,
                unit="bar",
                confidence=0.60,
                evidence=Evidence(page=1, text="Design pressure shall be minimum 10 bar"),
            ),
            RequirementCandidate(
                text="Motor power shall be minimum 10 kW",
                parameter="motor power",
                operator=">=",
                value=10,
                unit="kW",
                confidence=0.95,
                evidence=Evidence(page=1, text="Motor power shall be minimum 10 kW"),
            ),
        ],
    )

    result = validate_extraction(path, batch, min_confidence=0.75)
    assert result.items == []
    assert [rejected.reason for rejected in result.rejected] == [
        "confidence 0.600 is below minimum 0.750",
        "evidence text was not found on the declared source page",
    ]


def test_page_range_and_inconsistent_numeric_requirement_are_rejected(tmp_path):
    path = tmp_path / "spec.pdf"
    make_pdf(path, [["Noise level must not exceed 70 dB"]])
    batch = ExtractionBatch(
        provider="mock",
        kind=ExtractionKind.SPECIFICATION,
        candidates=[
            RequirementCandidate(
                text="Noise level must not exceed 70 dB",
                parameter="noise level",
                operator="<=",
                value=70,
                unit="dB",
                confidence=0.99,
                evidence=Evidence(page=2, text="Noise level must not exceed 70 dB"),
            ),
            RequirementCandidate(
                text="Noise level must not exceed 70 dB",
                parameter="noise level",
                operator="<=",
                value=None,
                unit="dB",
                confidence=0.99,
                evidence=Evidence(page=1, text="Noise level must not exceed 70 dB"),
            ),
        ],
    )

    result = validate_extraction(path, batch)
    assert result.items == []
    assert result.rejected[0].reason == "evidence page 2 is outside the source document"
    assert result.rejected[1].reason == "requirement operator and numeric value must be supplied together"


def test_vendor_candidate_flows_into_unchanged_deterministic_compare(tmp_path):
    specification = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    make_pdf(specification, [["Motor power shall be minimum 10 kW"]])
    make_pdf(vendor, [["Motor power: 11000 W"]])

    requirement_batch = ExtractionBatch(
        provider="mock",
        kind=ExtractionKind.SPECIFICATION,
        candidates=[
            RequirementCandidate(
                text="Motor power shall be minimum 10 kW",
                parameter="motor power",
                operator=">=",
                value=10,
                unit="kW",
                confidence=0.98,
                evidence=Evidence(page=1, text="Motor power shall be minimum 10 kW"),
            )
        ],
    )
    vendor_batch = ExtractionBatch(
        provider="mock",
        kind=ExtractionKind.VENDOR,
        candidates=[
            VendorFactCandidate(
                parameter="motor power",
                raw_value="11000 W",
                value=11000,
                unit="W",
                confidence=0.97,
                evidence=Evidence(page=1, text="Motor power: 11000 W"),
            )
        ],
    )

    requirements = validate_extraction(specification, requirement_batch).items
    facts = validate_extraction(vendor, vendor_batch).items
    report = compare(requirements, facts, specification.name, vendor.name)
    assert report.findings[0].status == Status.PASS
    assert report.compliance_score == 100.0


def test_candidate_type_must_match_batch_kind(tmp_path):
    path = tmp_path / "spec.pdf"
    make_pdf(path, [["Motor power shall be minimum 10 kW"]])
    batch = ExtractionBatch(
        provider="mock",
        kind=ExtractionKind.SPECIFICATION,
        candidates=[
            VendorFactCandidate(
                parameter="motor power",
                raw_value="11 kW",
                confidence=0.99,
                evidence=Evidence(page=1, text="Motor power shall be minimum 10 kW"),
            )
        ],
    )

    result = validate_extraction(path, batch)
    assert result.items == []
    assert result.rejected[0].reason == "candidate type does not match specification extraction"


def test_provider_identity_and_requested_kind_are_enforced(tmp_path):
    path = tmp_path / "vendor.pdf"
    make_pdf(path, [["Motor power: 11 kW"]])

    class WrongKindExtractor:
        name = "mock"

        def extract(self, document: Path, kind: ExtractionKind) -> ExtractionBatch:
            return ExtractionBatch(provider="mock", kind=ExtractionKind.SPECIFICATION)

    with pytest.raises(ValueError, match="provider returned"):
        extract_with_provider(path, ExtractionKind.VENDOR, WrongKindExtractor())

    class WrongNameExtractor:
        name = "expected"

        def extract(self, document: Path, kind: ExtractionKind) -> ExtractionBatch:
            return ExtractionBatch(provider="unexpected", kind=kind)

    with pytest.raises(ValueError, match="provider batch name"):
        extract_with_provider(path, ExtractionKind.VENDOR, WrongNameExtractor())


def test_invalid_minimum_confidence_is_rejected(tmp_path):
    path = tmp_path / "vendor.pdf"
    make_pdf(path, [["Motor power: 11 kW"]])
    batch = ExtractionBatch(provider="mock", kind=ExtractionKind.VENDOR)

    with pytest.raises(ValueError, match="min_confidence"):
        validate_extraction(path, batch, min_confidence=1.1)
