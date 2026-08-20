from __future__ import annotations

import pytest

import bidlint.vendor_package as vendor_package
from bidlint.document_policy import DocumentClass, classify_document
from bidlint.models import SourceRef, VendorFact
from bidlint.vendor_package import consolidate_package_facts, parse_vendor_package


def _fact(
    document: str,
    parameter: str,
    raw_value: str,
    *,
    value: float | None = None,
    unit: str | None = None,
    page: int | None = None,
    line: int | None = None,
) -> VendorFact:
    return VendorFact(
        parameter=parameter,
        raw_value=raw_value,
        value=value,
        unit=unit,
        source=SourceRef(document=document, page=page, line=line),
    )


def test_document_classification_is_deterministic() -> None:
    assert classify_document("Employer-Specification.pdf") is DocumentClass.SPECIFICATION
    assert classify_document("pump-datasheet.pdf") is DocumentClass.DATASHEET
    assert classify_document("compliance-matrix.xlsx") is DocumentClass.COMPLIANCE_SCHEDULE
    assert classify_document("technical-offer.pdf") is DocumentClass.TECHNICAL_OFFER
    assert classify_document("commercial-pricing.pdf") is DocumentClass.IGNORED
    assert classify_document("cover-letter.docx") is DocumentClass.IGNORED


def test_package_excludes_specification_and_explicitly_ignored_documents(tmp_path, monkeypatch) -> None:
    (tmp_path / "Employer-Specification.pdf").write_bytes(b"")
    (tmp_path / "pump-datasheet.pdf").write_bytes(b"")
    (tmp_path / "vendor-offer.pdf").write_bytes(b"")

    calls: list[str] = []

    def fake_pdf(path):
        calls.append(path.name)
        return [_fact(path.name, "flow rate", "20 L/s", value=20, unit="L/s")]

    monkeypatch.setattr(vendor_package, "parse_vendor_facts", fake_pdf)

    package = parse_vendor_package(tmp_path, document_classes={"vendor-offer.pdf": "ignored"})

    assert calls == ["pump-datasheet.pdf"]
    assert package.document_classes["Employer-Specification.pdf"] is DocumentClass.SPECIFICATION
    assert package.document_classes["vendor-offer.pdf"] is DocumentClass.IGNORED
    assert [path.name for path in package.ignored_documents] == ["vendor-offer.pdf"]


def test_explicit_priority_selects_higher_class_without_hidden_default() -> None:
    facts = [
        _fact("pump-datasheet.pdf", "flow rate", "20 L/s", value=20, unit="L/s", page=2),
        _fact("compliance.xlsx", "flow rate", "25 L/s", value=25, unit="L/s", line=7),
    ]
    document_classes = {
        "pump-datasheet.pdf": DocumentClass.DATASHEET,
        "compliance.xlsx": DocumentClass.COMPLIANCE_SCHEDULE,
    }

    default_facts, default_conflicts = consolidate_package_facts(
        "Supplier-A",
        facts,
        document_classes=document_classes,
    )
    prioritized_facts, prioritized_conflicts = consolidate_package_facts(
        "Supplier-A",
        facts,
        document_classes=document_classes,
        evidence_priority=(DocumentClass.COMPLIANCE_SCHEDULE, DocumentClass.DATASHEET),
    )

    assert default_facts == default_conflicts
    assert len(default_conflicts) == 1
    assert prioritized_facts == [facts[1]]
    assert prioritized_conflicts == []


def test_priority_does_not_break_tie_inside_same_class() -> None:
    facts = [
        _fact("schedule-a.xlsx", "flow rate", "20 L/s", value=20, unit="L/s", line=7),
        _fact("schedule-b.xlsx", "flow rate", "25 L/s", value=25, unit="L/s", line=9),
        _fact("pump-datasheet.pdf", "flow rate", "30 L/s", value=30, unit="L/s", page=2),
    ]
    document_classes = {
        "schedule-a.xlsx": DocumentClass.COMPLIANCE_SCHEDULE,
        "schedule-b.xlsx": DocumentClass.COMPLIANCE_SCHEDULE,
        "pump-datasheet.pdf": DocumentClass.DATASHEET,
    }

    consolidated, conflicts = consolidate_package_facts(
        "Supplier-A",
        facts,
        document_classes=document_classes,
        evidence_priority=(DocumentClass.COMPLIANCE_SCHEDULE, DocumentClass.DATASHEET),
    )

    assert consolidated == conflicts
    assert len(conflicts) == 1
    assert "schedule-a.xlsx:line 7 = 20 L/s" in conflicts[0].raw_value
    assert "schedule-b.xlsx:line 9 = 25 L/s" in conflicts[0].raw_value
    assert "pump-datasheet.pdf:page 2 = 30 L/s" in conflicts[0].raw_value


def test_invalid_policy_and_overrides_are_rejected(tmp_path) -> None:
    (tmp_path / "offer.pdf").write_bytes(b"")

    with pytest.raises(ValueError, match="does not match a package file"):
        parse_vendor_package(tmp_path, document_classes={"missing.pdf": "datasheet"})
    with pytest.raises(ValueError, match="evidence priority can only contain"):
        parse_vendor_package(tmp_path, evidence_priority=("specification",))
    with pytest.raises(ValueError, match="duplicate document classes"):
        parse_vendor_package(tmp_path, evidence_priority=("datasheet", "datasheet"))
