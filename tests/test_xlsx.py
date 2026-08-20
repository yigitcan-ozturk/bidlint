from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.cli import main
from bidlint.models import ComplianceReport, Finding, Requirement, SourceRef, Status, VendorFact
from bidlint.xlsx import portfolio_to_xlsx_bytes, write_portfolio_xlsx

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _q(tag: str) -> str:
    return f"{{{_MAIN_NS}}}{tag}"


def _requirement(requirement_id: str, parameter: str, value: float) -> Requirement:
    return Requirement(
        id=requirement_id,
        text=f"{parameter} shall be minimum {value:g} kW",
        parameter=parameter,
        operator=">=",
        value=value,
        unit="kw",
        source=SourceRef(document="spec.pdf", page=2, line=7),
    )


def _finding(
    requirement: Requirement,
    status: Status,
    offered: str | None,
    *,
    confidence: float = 1.0,
) -> Finding:
    fact = None
    if offered is not None:
        fact = VendorFact(
            parameter=requirement.parameter,
            raw_value=offered,
            value=float(offered.split()[0]),
            unit="kw",
            source=SourceRef(document="vendor.pdf", page=3, line=4, section="Ratings"),
        )
    return Finding(
        requirement=requirement,
        vendor_fact=fact,
        status=status,
        confidence=confidence,
        reason=f"{status.value} reason for {requirement.id}",
    )


def _reports() -> list[ComplianceReport]:
    motor = _requirement("R0001", "motor power", 10)
    standby = _requirement("R0002", "standby power", 5)
    vendor_a = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor-a.pdf",
        findings=[
            _finding(motor, Status.PASS, "11 kW"),
            _finding(standby, Status.DEVIATION, "4 kW", confidence=0.91),
        ],
    )
    vendor_b = ComplianceReport(
        specification="spec.pdf",
        vendor="vendor-b.pdf",
        findings=[
            _finding(motor, Status.PASS, "12 kW"),
            _finding(standby, Status.PASS, "6 kW"),
        ],
    )
    return [vendor_a, vendor_b]


def _inline_text(cell: ET.Element) -> str:
    text = cell.find(f"{_q('is')}/{_q('t')}")
    return text.text if text is not None and text.text is not None else ""


def _sheet_cells(xml_bytes: bytes) -> dict[str, str]:
    root = ET.fromstring(xml_bytes)
    values: dict[str, str] = {}
    for cell in root.findall(f".//{_q('c')}"):
        reference = cell.attrib["r"]
        if cell.attrib.get("t") == "inlineStr":
            values[reference] = _inline_text(cell)
        else:
            raw = cell.find(_q("v"))
            values[reference] = raw.text if raw is not None and raw.text is not None else ""
    return values


def _make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.save()


def test_xlsx_package_is_deterministic_and_contains_expected_sheets():
    first = portfolio_to_xlsx_bytes(_reports())
    second = portfolio_to_xlsx_bytes(_reports())
    assert first == second
    assert first.startswith(b"PK")

    with zipfile.ZipFile(BytesIO(first)) as archive:
        assert set(archive.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/_rels/workbook.xml.rels",
            "xl/styles.xml",
            "xl/workbook.xml",
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/worksheets/sheet3.xml",
        }
        for name in archive.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(archive.read(name))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall(f"{_q('sheets')}/{_q('sheet')}")
        assert [sheet.attrib["name"] for sheet in sheets] == ["Ranking", "Matrix", "Audit"]
        assert [sheet.attrib[f"{{{_REL_NS}}}id"] for sheet in sheets] == ["rId1", "rId2", "rId3"]


def test_xlsx_ranking_matrix_and_audit_preserve_deterministic_evidence():
    payload = portfolio_to_xlsx_bytes(_reports())
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        ranking = _sheet_cells(archive.read("xl/worksheets/sheet1.xml"))
        matrix = _sheet_cells(archive.read("xl/worksheets/sheet2.xml"))
        audit = _sheet_cells(archive.read("xl/worksheets/sheet3.xml"))

        assert ranking["B5"] == "vendor-b.pdf"
        assert ranking["C5"] == "100"
        assert ranking["B6"] == "vendor-a.pdf"
        assert ranking["C6"] == "50"

        assert matrix["D4"] == "vendor-b.pdf"
        assert matrix["E4"] == "vendor-a.pdf"
        assert matrix["D5"].startswith("PASS\n12 kW\n")
        assert matrix["E6"].startswith("DEVIATION\n4 kW\n")

        assert audit["B5"] == "vendor-b.pdf"
        assert audit["D5"] == "PASS"
        assert audit["J5"] == "2"
        assert audit["L5"] == "3"
        assert audit["M5"] == "Ratings"
        assert "PASS reason" in audit["N5"]

        for sheet_name in ["sheet1.xml", "sheet2.xml", "sheet3.xml"]:
            root = ET.fromstring(archive.read(f"xl/worksheets/{sheet_name}"))
            children = [child.tag.rsplit("}", 1)[-1] for child in root]
            assert children.index("autoFilter") < children.index("mergeCells")
            assert root.find(f".//{_q('f')}") is None


def test_xlsx_writer_validates_portfolio_contract(tmp_path):
    report = _reports()[0]
    other_spec = ComplianceReport(
        specification="other-spec.pdf",
        vendor="vendor-c.pdf",
        findings=report.findings,
    )

    with pytest.raises(ValueError, match="at least one"):
        portfolio_to_xlsx_bytes([])
    with pytest.raises(ValueError, match="same specification"):
        portfolio_to_xlsx_bytes([report, other_spec])
    with pytest.raises(ValueError, match="must end in .xlsx"):
        write_portfolio_xlsx([report], tmp_path / "tabulation.xls")


def test_rank_cli_writes_xlsx_without_changing_terminal_ranking(tmp_path, capsys):
    specification = tmp_path / "specification.pdf"
    vendor_a = tmp_path / "vendor-a.pdf"
    vendor_b = tmp_path / "vendor-b.pdf"
    output = tmp_path / "technical-tabulation.xlsx"

    _make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    _make_pdf(vendor_a, ["Motor power: 9 kW"])
    _make_pdf(vendor_b, ["Motor power: 11 kW"])

    result = main(
        [
            "rank",
            str(specification),
            str(vendor_a),
            str(vendor_b),
            "--output",
            str(output),
        ]
    )

    terminal = capsys.readouterr().out
    assert result == 0
    assert output.read_bytes().startswith(b"PK")
    assert "BIDLINT — VENDOR RANKING" in terminal
    assert "vendor-b.pdf" in terminal
    assert "vendor-a.pdf" in terminal
