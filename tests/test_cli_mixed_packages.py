from __future__ import annotations

from types import SimpleNamespace

import bidlint.cli as cli
from bidlint.models import Requirement, SourceRef, VendorFact


def _args() -> SimpleNamespace:
    return SimpleNamespace(
        ifc_class="IfcPump",
        ifc_guid="PUMP-GUID",
        ifc_pset="Pset_PumpCommon",
        xlsx_sheet="Offer",
    )


def _fact() -> VendorFact:
    return VendorFact(
        parameter="flow rate",
        raw_value="20 L/s",
        value=20,
        unit="L/s",
        source=SourceRef(document="offer.pdf", page=1),
    )


def _requirement() -> Requirement:
    return Requirement(
        id="R0001",
        text="Flow rate shall be minimum 10 L/s.",
        parameter="flow rate",
        operator=">=",
        value=10,
        unit="L/s",
    )


def test_package_evidence_suffix_detection_respects_document_classification(tmp_path) -> None:
    (tmp_path / "Employer-Specification.ifc").write_bytes(b"")
    (tmp_path / "pump-model.ifc").write_bytes(b"")
    (tmp_path / "commercial-pricing.xlsx").write_bytes(b"")
    (tmp_path / "compliance-schedule.xlsx").write_bytes(b"")

    assert cli._vendor_has_evidence_suffix(str(tmp_path), ".ifc") is True
    assert cli._vendor_has_evidence_suffix(str(tmp_path), ".xlsx") is True

    (tmp_path / "pump-model.ifc").unlink()
    (tmp_path / "compliance-schedule.xlsx").unlink()

    assert cli._vendor_has_evidence_suffix(str(tmp_path), ".ifc") is False
    assert cli._vendor_has_evidence_suffix(str(tmp_path), ".xlsx") is False


def test_mixed_rank_scopes_selectors_to_relevant_package_types(tmp_path, monkeypatch) -> None:
    ifc_package = tmp_path / "IfcSupplier"
    ifc_package.mkdir()
    (ifc_package / "pump-model.ifc").write_bytes(b"")

    xlsx_package = tmp_path / "XlsxSupplier"
    xlsx_package.mkdir()
    (xlsx_package / "compliance-schedule.xlsx").write_bytes(b"")

    pdf_package = tmp_path / "PdfSupplier"
    pdf_package.mkdir()
    (pdf_package / "technical-offer.pdf").write_bytes(b"")

    seen: dict[str, dict[str, object]] = {}

    def fake_parse_vendor_input(path, **kwargs):
        seen[str(path)] = kwargs
        return []

    monkeypatch.setattr(cli, "parse_vendor_input", fake_parse_vendor_input)
    aliases = {"supplier flow": "flow rate"}
    args = _args()

    cli._parse_cli_vendor(str(ifc_package), args, mixed_rank=True, aliases=aliases)
    cli._parse_cli_vendor(str(xlsx_package), args, mixed_rank=True, aliases=aliases)
    cli._parse_cli_vendor(str(pdf_package), args, mixed_rank=True, aliases=aliases)

    assert seen[str(ifc_package)] == {
        "ifc_class": "IfcPump",
        "ifc_guid": "PUMP-GUID",
        "ifc_pset": "Pset_PumpCommon",
        "xlsx_sheet": None,
        "aliases": aliases,
    }
    assert seen[str(xlsx_package)] == {
        "ifc_class": None,
        "ifc_guid": None,
        "ifc_pset": None,
        "xlsx_sheet": "Offer",
        "aliases": aliases,
    }
    assert seen[str(pdf_package)] == {
        "ifc_class": None,
        "ifc_guid": None,
        "ifc_pset": None,
        "xlsx_sheet": None,
        "aliases": aliases,
    }


def test_rank_validation_accepts_ifc_and_xlsx_evidence_inside_packages(tmp_path, monkeypatch) -> None:
    ifc_package = tmp_path / "IfcSupplier"
    ifc_package.mkdir()
    (ifc_package / "pump-model.ifc").write_bytes(b"")

    xlsx_package = tmp_path / "XlsxSupplier"
    xlsx_package.mkdir()
    (xlsx_package / "compliance-schedule.xlsx").write_bytes(b"")

    monkeypatch.setattr(cli, "parse_requirements", lambda _: [_requirement()])
    monkeypatch.setattr(cli, "_parse_cli_vendor", lambda *args, **kwargs: [_fact()])

    assert (
        cli.main(
            [
                "rank",
                "spec.pdf",
                str(ifc_package),
                str(xlsx_package),
                "--ifc-class",
                "IfcPump",
                "--xlsx-sheet",
                "Offer",
            ]
        )
        == 0
    )


def test_rank_validation_ignores_non_evidence_ifc_and_xlsx_package_files(tmp_path, monkeypatch) -> None:
    package_a = tmp_path / "Supplier-A"
    package_a.mkdir()
    (package_a / "Employer-Specification.ifc").write_bytes(b"")

    package_b = tmp_path / "Supplier-B"
    package_b.mkdir()
    (package_b / "commercial-pricing.xlsx").write_bytes(b"")

    monkeypatch.setattr(cli, "parse_requirements", lambda _: [_requirement()])

    try:
        cli.main(
            [
                "rank",
                "spec.pdf",
                str(package_a),
                str(package_b),
                "--ifc-class",
                "IfcPump",
            ]
        )
    except SystemExit as exc:
        assert "package evidence file" in str(exc)
    else:
        raise AssertionError("non-evidence IFC files must not satisfy rank selector validation")
