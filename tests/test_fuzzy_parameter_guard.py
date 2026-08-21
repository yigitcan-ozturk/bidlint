from __future__ import annotations

from bidlint.compare import compare
from bidlint.models import Requirement, Status, VendorFact


def test_unrelated_similar_spelling_does_not_create_vendor_evidence() -> None:
    report = compare(
        [Requirement(id="R0001", text="Grating: plain ladder grating", parameter="grating")],
        [VendorFact(parameter="drawings", raw_value="General arrangement drawings provided")],
        "specification.xlsx",
        "vendor.xlsx",
    )

    finding = report.findings[0]
    assert finding.status is Status.MISSING
    assert finding.vendor_fact is None
    assert finding.confidence == 0.0


def test_minor_typo_without_token_overlap_still_matches() -> None:
    report = compare(
        [Requirement(id="R0001", text="Grating: plain ladder grating", parameter="grating")],
        [VendorFact(parameter="gratting", raw_value="Plain ladder grating")],
        "specification.xlsx",
        "vendor.xlsx",
    )

    finding = report.findings[0]
    assert finding.status is Status.REVIEW
    assert finding.vendor_fact is not None
    assert finding.confidence >= 0.8


def test_shared_parameter_tokens_keep_existing_fuzzy_behavior() -> None:
    report = compare(
        [Requirement(id="R0001", text="Motor power", parameter="motor power")],
        [VendorFact(parameter="rated motor power", raw_value="11 kW")],
        "specification.pdf",
        "vendor.pdf",
    )

    finding = report.findings[0]
    assert finding.status is Status.REVIEW
    assert finding.vendor_fact is not None
    assert finding.confidence >= 0.52
