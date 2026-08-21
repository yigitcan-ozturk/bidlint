from __future__ import annotations

import warnings
import zipfile
from pathlib import Path

import pytest

from bidlint import entrypoint, ifc
from bidlint.inputs import parse_vendor_input
from bidlint.xlsx_input import parse_xlsx_vendor_facts

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def test_malformed_pdf_is_rejected_with_stable_input_error(tmp_path, capsys):
    path = tmp_path / "truncated.pdf"
    path.write_bytes(b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\n")

    with pytest.raises(ValueError, match="invalid PDF input"):
        parse_vendor_input(path)

    assert entrypoint.main(["extract", str(path), "--kind", "vendor"]) == 3
    assert "input_error" in capsys.readouterr().err


def test_invalid_xlsx_zip_is_rejected(tmp_path):
    path = tmp_path / "invalid.xlsx"
    path.write_bytes(b"not-an-ooxml-archive")

    with pytest.raises(ValueError, match="invalid XLSX vendor input"):
        parse_xlsx_vendor_facts(path)


def test_xlsx_duplicate_package_entries_are_rejected(tmp_path):
    path = tmp_path / "duplicate.xlsx"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("xl/workbook.xml", "<workbook />")
            archive.writestr("xl/workbook.xml", "<workbook />")
            archive.writestr("xl/_rels/workbook.xml.rels", "<Relationships />")

    with pytest.raises(ValueError, match="duplicate package entries"):
        parse_xlsx_vendor_facts(path)


def test_xlsx_relationship_cannot_escape_package(tmp_path):
    path = tmp_path / "escape.xlsx"
    workbook = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{_MAIN_NS}" xmlns:r="{_REL_NS}">
  <sheets><sheet name="Offer" sheetId="1" r:id="rId1" /></sheets>
</workbook>
"""
    relationships = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{_PACKAGE_REL_NS}">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="../../escape.xml" />
</Relationships>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)

    with pytest.raises(ValueError, match="workbook relationship target|escapes workbook package"):
        parse_xlsx_vendor_facts(path)


def test_ifc_parser_normalizes_model_open_failure(tmp_path, monkeypatch):
    path = tmp_path / "malformed.ifc"
    path.write_text("ISO-10303-21;\nDATA;\nmalformed", encoding="utf-8")

    class BrokenIfcApi:
        @staticmethod
        def open(_path: str):
            raise RuntimeError("malformed model")

    monkeypatch.setattr(ifc, "_load_ifc_api", lambda: (BrokenIfcApi, lambda *args, **kwargs: {}))

    with pytest.raises(ValueError, match="unable to open IFC file"):
        ifc.parse_ifc_facts(path, ifc_class="IfcPump")
