from __future__ import annotations

import bidlint.vendor_package as vendor_package
from bidlint.document_policy import DocumentClass
from bidlint.models import SourceRef, VendorFact
from bidlint.vendor_package import EvidenceDisposition, parse_vendor_package


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


def test_package_audit_marks_selected_duplicates_and_lower_priority(tmp_path, monkeypatch) -> None:
    (tmp_path / "a-compliance.xlsx").write_bytes(b"")
    (tmp_path / "b-datasheet.pdf").write_bytes(b"")
    (tmp_path / "c-offer.pdf").write_bytes(b"")

    compliance = _fact("a-compliance.xlsx", "supplier rated output", "11 kW", value=11, unit="kW", line=3)
    datasheet = _fact("b-datasheet.pdf", "motor power", "11000 W", value=11000, unit="W", page=2)
    offer = _fact("c-offer.pdf", "motor power", "15 kW", value=15, unit="kW", page=4)

    def fake_xlsx(path, *, sheet=None):
        assert path.name == "a-compliance.xlsx"
        return [compliance]

    def fake_pdf(path):
        return {
            "b-datasheet.pdf": [datasheet],
            "c-offer.pdf": [offer],
        }[path.name]

    monkeypatch.setattr(vendor_package, "parse_xlsx_vendor_facts", fake_xlsx)
    monkeypatch.setattr(vendor_package, "parse_vendor_facts", fake_pdf)

    package = parse_vendor_package(
        tmp_path,
        aliases={"supplier rated output": "motor power"},
        evidence_priority=(DocumentClass.COMPLIANCE_SCHEDULE, DocumentClass.DATASHEET),
    )

    assert package.facts == [compliance]
    assert package.conflicts == []
    assert [entry.fact for entry in package.evidence_audit] == [compliance, datasheet, offer]
    assert [entry.canonical_parameter for entry in package.evidence_audit] == [
        "motor power",
        "motor power",
        "motor power",
    ]
    assert [entry.disposition for entry in package.evidence_audit] == [
        EvidenceDisposition.SELECTED,
        EvidenceDisposition.LOWER_PRIORITY,
        EvidenceDisposition.LOWER_PRIORITY,
    ]
    assert [entry.priority_rank for entry in package.evidence_audit] == [1, 2, None]


def test_package_audit_marks_same_priority_conflicts(tmp_path, monkeypatch) -> None:
    (tmp_path / "a-compliance.xlsx").write_bytes(b"")
    (tmp_path / "b-compliance.xlsx").write_bytes(b"")

    first = _fact("a-compliance.xlsx", "flow rate", "20 L/s", value=20, unit="L/s", line=3)
    second = _fact("b-compliance.xlsx", "flow rate", "25 L/s", value=25, unit="L/s", line=5)

    def fake_xlsx(path, *, sheet=None):
        return {
            "a-compliance.xlsx": [first],
            "b-compliance.xlsx": [second],
        }[path.name]

    monkeypatch.setattr(vendor_package, "parse_xlsx_vendor_facts", fake_xlsx)

    package = parse_vendor_package(
        tmp_path,
        evidence_priority=(DocumentClass.COMPLIANCE_SCHEDULE, DocumentClass.DATASHEET),
    )

    assert len(package.conflicts) == 1
    assert [entry.disposition for entry in package.evidence_audit] == [
        EvidenceDisposition.CONFLICT,
        EvidenceDisposition.CONFLICT,
    ]
    assert [entry.priority_rank for entry in package.evidence_audit] == [1, 1]


def test_package_audit_marks_equivalent_duplicates_without_priority(tmp_path, monkeypatch) -> None:
    (tmp_path / "a-datasheet.pdf").write_bytes(b"")
    (tmp_path / "b-offer.pdf").write_bytes(b"")

    first = _fact("a-datasheet.pdf", "motor power", "11 kW", value=11, unit="kW", page=2)
    second = _fact("b-offer.pdf", "rated motor power", "11000 W", value=11000, unit="W", page=4)

    def fake_pdf(path):
        return {
            "a-datasheet.pdf": [first],
            "b-offer.pdf": [second],
        }[path.name]

    monkeypatch.setattr(vendor_package, "parse_vendor_facts", fake_pdf)

    package = parse_vendor_package(tmp_path)

    assert package.facts == [first]
    assert [entry.disposition for entry in package.evidence_audit] == [
        EvidenceDisposition.SELECTED,
        EvidenceDisposition.EQUIVALENT_DUPLICATE,
    ]
    assert [entry.priority_rank for entry in package.evidence_audit] == [None, None]


def test_package_audit_dict_is_json_ready_and_preserves_provenance(tmp_path, monkeypatch) -> None:
    (tmp_path / "pump-datasheet.pdf").write_bytes(b"")
    fact = _fact("pump-datasheet.pdf", "flow rate", "20 L/s", value=20, unit="L/s", page=7)

    monkeypatch.setattr(vendor_package, "parse_vendor_facts", lambda path: [fact])

    package = parse_vendor_package(tmp_path)
    payload = package.to_audit_dict()

    assert payload["documents"] == [
        {
            "document": "pump-datasheet.pdf",
            "document_class": "datasheet",
        }
    ]
    assert payload["evidence"][0]["disposition"] == "selected"
    assert payload["evidence"][0]["fact"]["source"] == {
        "document": "pump-datasheet.pdf",
        "page": 7,
        "line": None,
        "section": None,
    }
    assert payload["consolidated_facts"][0]["parameter"] == "flow rate"
