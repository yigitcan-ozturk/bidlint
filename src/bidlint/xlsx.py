from __future__ import annotations

import math
import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from . import __version__
from .models import ComplianceReport, Finding, Requirement, Status
from .portfolio import rank_reports

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_MAX_ROWS = 1_048_576
_MAX_COLS = 16_384
_MAX_CELL_TEXT = 32_767

ET.register_namespace("", _MAIN_NS)
ET.register_namespace("r", _REL_NS)


def _q(tag: str) -> str:
    return f"{{{_MAIN_NS}}}{tag}"


def _xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _excel_text(value: object) -> str:
    text = _ILLEGAL_XML.sub("", str(value))
    if len(text) > _MAX_CELL_TEXT:
        text = text[: _MAX_CELL_TEXT - 1] + "…"
    return text


def _column_name(index: int) -> str:
    if index < 1 or index > _MAX_COLS:
        raise ValueError("workbook column limit exceeded")
    letters: list[str] = []
    value = index
    while value:
        value, remainder = divmod(value - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def _cell(reference: str, value: object, *, style: int = 4) -> ET.Element:
    attrs = {"r": reference, "s": str(style)}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"non-finite workbook value at {reference}")
        cell = ET.Element(_q("c"), attrs)
        raw = ET.SubElement(cell, _q("v"))
        raw.text = f"{numeric:g}"
        return cell

    cell = ET.Element(_q("c"), {**attrs, "t": "inlineStr"})
    inline = ET.SubElement(cell, _q("is"))
    text = ET.SubElement(inline, _q("t"))
    text.set(_XML_SPACE, "preserve")
    text.text = _excel_text(value)
    return cell


def _append_row(
    sheet_data: ET.Element,
    row_number: int,
    values: list[object],
    *,
    styles: list[int] | None = None,
    height: float | None = None,
) -> None:
    if row_number > _MAX_ROWS:
        raise ValueError("workbook row limit exceeded")
    attrs = {"r": str(row_number)}
    if height is not None:
        attrs.update({"ht": f"{height:g}", "customHeight": "1"})
    row = ET.SubElement(sheet_data, _q("row"), attrs)
    for column, value in enumerate(values, start=1):
        style = styles[column - 1] if styles and column <= len(styles) else 4
        row.append(_cell(f"{_column_name(column)}{row_number}", value, style=style))


def _required_text(requirement: Requirement) -> str:
    if requirement.value is None:
        return "qualitative"
    return f"{requirement.operator or ''} {requirement.value:g}{requirement.unit or ''}".strip()


def _requirements(reports: list[ComplianceReport]) -> list[Requirement]:
    ordered: list[Requirement] = []
    seen: set[str] = set()
    for report in reports:
        for finding in report.findings:
            requirement = finding.requirement
            if requirement.id not in seen:
                seen.add(requirement.id)
                ordered.append(requirement)
    return ordered


def _style_for_status(status: Status) -> int:
    return {
        Status.PASS: 7,
        Status.DEVIATION: 8,
        Status.MISSING: 9,
        Status.REVIEW: 10,
    }[status]


def _base_worksheet(*, freeze_rows: int, freeze_columns: int = 0) -> tuple[ET.Element, ET.Element]:
    root = ET.Element(_q("worksheet"))
    views = ET.SubElement(root, _q("sheetViews"))
    view = ET.SubElement(views, _q("sheetView"), {"workbookViewId": "0"})
    if freeze_rows or freeze_columns:
        attrs: dict[str, str] = {"state": "frozen"}
        if freeze_rows:
            attrs["ySplit"] = str(freeze_rows)
        if freeze_columns:
            attrs["xSplit"] = str(freeze_columns)
        attrs["topLeftCell"] = f"{_column_name(freeze_columns + 1)}{freeze_rows + 1}"
        attrs["activePane"] = "bottomRight" if freeze_rows and freeze_columns else (
            "bottomLeft" if freeze_rows else "topRight"
        )
        ET.SubElement(view, _q("pane"), attrs)
    ET.SubElement(root, _q("sheetFormatPr"), {"defaultRowHeight": "15"})
    sheet_data = ET.SubElement(root, _q("sheetData"))
    return root, sheet_data


def _add_columns(root: ET.Element, widths: list[float]) -> None:
    cols = ET.Element(_q("cols"))
    for index, width in enumerate(widths, start=1):
        ET.SubElement(
            cols,
            _q("col"),
            {"min": str(index), "max": str(index), "width": f"{width:g}", "customWidth": "1"},
        )
    sheet_data = root.find(_q("sheetData"))
    assert sheet_data is not None
    root.insert(list(root).index(sheet_data), cols)


def _add_merge(root: ET.Element, reference: str) -> None:
    merges = root.find(_q("mergeCells"))
    if merges is None:
        merges = ET.SubElement(root, _q("mergeCells"), {"count": "0"})
    ET.SubElement(merges, _q("mergeCell"), {"ref": reference})
    merges.set("count", str(len(merges)))


def _add_filter(root: ET.Element, reference: str) -> None:
    ET.SubElement(root, _q("autoFilter"), {"ref": reference})


def _ranking_sheet(ranked: list[ComplianceReport]) -> bytes:
    root, data = _base_worksheet(freeze_rows=4)
    _add_columns(root, [8, 34, 14, 11, 13, 11, 11])

    _append_row(data, 1, ["bidlint technical bid tabulation"], styles=[1], height=28)
    _append_row(data, 2, ["Specification", ranked[0].specification], styles=[2, 4])
    _append_row(data, 3, ["Generated by", f"bidlint v{__version__}"], styles=[2, 4])
    headers = ["Rank", "Vendor", "Score", "PASS", "DEVIATION", "MISSING", "REVIEW"]
    _append_row(data, 4, headers, styles=[3] * len(headers), height=22)

    for rank, report in enumerate(ranked, start=1):
        counts = report.counts
        row = 4 + rank
        _append_row(
            data,
            row,
            [
                rank,
                report.vendor,
                report.compliance_score,
                counts["PASS"],
                counts["DEVIATION"],
                counts["MISSING"],
                counts["REVIEW"],
            ],
            styles=[6, 4, 5, 6, 6, 6, 6],
        )

    note_row = 6 + len(ranked)
    _append_row(
        data,
        note_row,
        ["Technical ranking only. Commercial price, delivery, payment terms and final engineering acceptance are outside bidlint."],
        styles=[11],
        height=30,
    )
    _add_merge(root, "A1:G1")
    _add_merge(root, f"A{note_row}:G{note_row}")
    _add_filter(root, f"A4:G{4 + len(ranked)}")
    return _xml_bytes(root)


def _matrix_sheet(ranked: list[ComplianceReport], requirements: list[Requirement]) -> bytes:
    column_count = 3 + len(ranked)
    if column_count > _MAX_COLS:
        raise ValueError("too many vendors for XLSX matrix")
    root, data = _base_worksheet(freeze_rows=4, freeze_columns=3)
    _add_columns(root, [14, 28, 18] + [36] * len(ranked))

    last_column = _column_name(column_count)
    _append_row(data, 1, ["requirement-by-vendor matrix"], styles=[1], height=28)
    _append_row(data, 2, ["Specification", ranked[0].specification], styles=[2, 4])
    _append_row(
        data,
        3,
        ["Cell format", "STATUS / offered value / deterministic reason"],
        styles=[2, 11],
        height=28,
    )
    headers = ["Requirement", "Parameter", "Required", *[report.vendor for report in ranked]]
    _append_row(data, 4, headers, styles=[3] * len(headers), height=34)

    vendor_maps = [
        {finding.requirement.id: finding for finding in report.findings}
        for report in ranked
    ]
    for offset, requirement in enumerate(requirements, start=1):
        values: list[object] = [requirement.id, requirement.parameter, _required_text(requirement)]
        styles = [4, 4, 4]
        for finding_map in vendor_maps:
            finding = finding_map.get(requirement.id)
            if finding is None:
                values.append("MISSING\n—\nNo finding")
                styles.append(9)
                continue
            offered = finding.vendor_fact.raw_value if finding.vendor_fact else "—"
            values.append(f"{finding.status.value}\n{offered}\n{finding.reason}")
            styles.append(_style_for_status(finding.status))
        _append_row(data, 4 + offset, values, styles=styles, height=54)

    _add_merge(root, f"A1:{last_column}1")
    _add_filter(root, f"A4:{last_column}{4 + len(requirements)}")
    return _xml_bytes(root)


def _audit_sheet(ranked: list[ComplianceReport]) -> bytes:
    headers = [
        "Rank",
        "Vendor",
        "Score",
        "Status",
        "Requirement ID",
        "Parameter",
        "Required",
        "Offered",
        "Confidence",
        "Spec Page",
        "Spec Section",
        "Vendor Page",
        "Vendor Section",
        "Reason",
    ]
    row_count = 4 + sum(len(report.findings) for report in ranked)
    if row_count > _MAX_ROWS:
        raise ValueError("too many findings for XLSX audit sheet")

    root, data = _base_worksheet(freeze_rows=4)
    _add_columns(root, [8, 30, 12, 14, 16, 28, 18, 24, 13, 12, 26, 12, 28, 54])
    last_column = _column_name(len(headers))

    _append_row(data, 1, ["technical compliance audit"], styles=[1], height=28)
    _append_row(data, 2, ["Specification", ranked[0].specification], styles=[2, 4])
    _append_row(data, 3, ["Generated by", f"bidlint v{__version__}"], styles=[2, 4])
    _append_row(data, 4, headers, styles=[3] * len(headers), height=28)

    row = 5
    for rank, report in enumerate(ranked, start=1):
        for finding in report.findings:
            requirement = finding.requirement
            fact = finding.vendor_fact
            spec_source = requirement.source
            vendor_source = fact.source if fact else None
            status_style = _style_for_status(finding.status)
            _append_row(
                data,
                row,
                [
                    rank,
                    report.vendor,
                    report.compliance_score,
                    finding.status.value,
                    requirement.id,
                    requirement.parameter,
                    _required_text(requirement),
                    fact.raw_value if fact else "",
                    finding.confidence,
                    spec_source.page if spec_source and spec_source.page is not None else "",
                    spec_source.section if spec_source and spec_source.section else "",
                    vendor_source.page if vendor_source and vendor_source.page is not None else "",
                    vendor_source.section if vendor_source and vendor_source.section else "",
                    finding.reason,
                ],
                styles=[6, 4, 5, status_style, 4, 4, 4, 4, 12, 6, 11, 6, 11, 11],
                height=34,
            )
            row += 1

    _add_merge(root, f"A1:{last_column}1")
    _add_filter(root, f"A4:{last_column}{row - 1}")
    return _xml_bytes(root)


def _styles_xml() -> bytes:
    root = ET.Element(_q("styleSheet"))
    num_fmts = ET.SubElement(root, _q("numFmts"), {"count": "2"})
    ET.SubElement(num_fmts, _q("numFmt"), {"numFmtId": "164", "formatCode": '0.0"%"'})
    ET.SubElement(num_fmts, _q("numFmt"), {"numFmtId": "165", "formatCode": "0.000"})

    fonts = ET.SubElement(root, _q("fonts"), {"count": "3"})
    font = ET.SubElement(fonts, _q("font"))
    ET.SubElement(font, _q("sz"), {"val": "11"})
    ET.SubElement(font, _q("name"), {"val": "Calibri"})
    ET.SubElement(font, _q("family"), {"val": "2"})
    title = ET.SubElement(fonts, _q("font"))
    ET.SubElement(title, _q("b"))
    ET.SubElement(title, _q("sz"), {"val": "18"})
    ET.SubElement(title, _q("color"), {"rgb": "FFFFFFFF"})
    ET.SubElement(title, _q("name"), {"val": "Calibri"})
    header = ET.SubElement(fonts, _q("font"))
    ET.SubElement(header, _q("b"))
    ET.SubElement(header, _q("sz"), {"val": "11"})
    ET.SubElement(header, _q("color"), {"rgb": "FFFFFFFF"})
    ET.SubElement(header, _q("name"), {"val": "Calibri"})

    fills = ET.SubElement(root, _q("fills"), {"count": "8"})
    fill = ET.SubElement(fills, _q("fill"))
    ET.SubElement(fill, _q("patternFill"), {"patternType": "none"})
    fill = ET.SubElement(fills, _q("fill"))
    ET.SubElement(fill, _q("patternFill"), {"patternType": "gray125"})
    for color in ["FF111318", "FF334155", "FFE9F8EF", "FFFDECEC", "FFFFF4DA", "FFEDF0FF"]:
        fill = ET.SubElement(fills, _q("fill"))
        pattern = ET.SubElement(fill, _q("patternFill"), {"patternType": "solid"})
        ET.SubElement(pattern, _q("fgColor"), {"rgb": color})
        ET.SubElement(pattern, _q("bgColor"), {"indexed": "64"})

    borders = ET.SubElement(root, _q("borders"), {"count": "2"})
    border = ET.SubElement(borders, _q("border"))
    for edge in ["left", "right", "top", "bottom", "diagonal"]:
        ET.SubElement(border, _q(edge))
    border = ET.SubElement(borders, _q("border"))
    for edge in ["left", "right", "top", "bottom"]:
        element = ET.SubElement(border, _q(edge), {"style": "thin"})
        ET.SubElement(element, _q("color"), {"rgb": "FFE2E8F0"})
    ET.SubElement(border, _q("diagonal"))

    cell_style_xfs = ET.SubElement(root, _q("cellStyleXfs"), {"count": "1"})
    ET.SubElement(cell_style_xfs, _q("xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"})
    cell_xfs = ET.SubElement(root, _q("cellXfs"), {"count": "13"})

    def add_xf(
        *,
        num_fmt: int = 0,
        font_id: int = 0,
        fill_id: int = 0,
        border_id: int = 0,
        horizontal: str | None = None,
        vertical: str | None = None,
        wrap: bool = False,
    ) -> None:
        attrs = {
            "numFmtId": str(num_fmt),
            "fontId": str(font_id),
            "fillId": str(fill_id),
            "borderId": str(border_id),
            "xfId": "0",
        }
        if num_fmt:
            attrs["applyNumberFormat"] = "1"
        if font_id:
            attrs["applyFont"] = "1"
        if fill_id:
            attrs["applyFill"] = "1"
        if border_id:
            attrs["applyBorder"] = "1"
        xf = ET.SubElement(cell_xfs, _q("xf"), attrs)
        if horizontal or vertical or wrap:
            alignment_attrs: dict[str, str] = {}
            if horizontal:
                alignment_attrs["horizontal"] = horizontal
            if vertical:
                alignment_attrs["vertical"] = vertical
            if wrap:
                alignment_attrs["wrapText"] = "1"
            ET.SubElement(xf, _q("alignment"), alignment_attrs)
            xf.set("applyAlignment", "1")

    add_xf()  # 0 default
    add_xf(font_id=1, fill_id=2, vertical="center")  # 1 title
    add_xf(font_id=2, vertical="center")  # 2 metadata label
    add_xf(font_id=2, fill_id=3, border_id=1, horizontal="center", vertical="center", wrap=True)  # 3 header
    add_xf(border_id=1, vertical="top")  # 4 body
    add_xf(num_fmt=164, border_id=1, horizontal="right", vertical="top")  # 5 percentage-points score
    add_xf(border_id=1, horizontal="right", vertical="top")  # 6 integer
    add_xf(fill_id=4, border_id=1, vertical="top", wrap=True)  # 7 pass
    add_xf(fill_id=5, border_id=1, vertical="top", wrap=True)  # 8 deviation
    add_xf(fill_id=6, border_id=1, vertical="top", wrap=True)  # 9 missing
    add_xf(fill_id=7, border_id=1, vertical="top", wrap=True)  # 10 review
    add_xf(border_id=1, vertical="top", wrap=True)  # 11 wrapped body
    add_xf(num_fmt=165, border_id=1, horizontal="right", vertical="top")  # 12 confidence

    cell_styles = ET.SubElement(root, _q("cellStyles"), {"count": "1"})
    ET.SubElement(cell_styles, _q("cellStyle"), {"name": "Normal", "xfId": "0", "builtinId": "0"})
    ET.SubElement(root, _q("dxfs"), {"count": "0"})
    ET.SubElement(root, _q("tableStyles"), {"count": "0", "defaultTableStyle": "TableStyleMedium2", "defaultPivotStyle": "PivotStyleLight16"})
    return _xml_bytes(root)


def _workbook_xml() -> bytes:
    root = ET.Element(_q("workbook"))
    ET.SubElement(root, _q("workbookPr"))
    views = ET.SubElement(root, _q("bookViews"))
    ET.SubElement(views, _q("workbookView"), {"xWindow": "0", "yWindow": "0", "windowWidth": "24000", "windowHeight": "12000"})
    sheets = ET.SubElement(root, _q("sheets"))
    for index, name in enumerate(["Ranking", "Matrix", "Audit"], start=1):
        ET.SubElement(
            sheets,
            _q("sheet"),
            {"name": name, "sheetId": str(index), f"{{{_REL_NS}}}id": f"rId{index}"},
        )
    ET.SubElement(root, _q("calcPr"), {"calcId": "0", "fullCalcOnLoad": "0"})
    return _xml_bytes(root)


def _workbook_rels_xml() -> bytes:
    root = ET.Element("Relationships", xmlns=_PACKAGE_REL_NS)
    for index in range(1, 4):
        ET.SubElement(
            root,
            "Relationship",
            {
                "Id": f"rId{index}",
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
                "Target": f"worksheets/sheet{index}.xml",
            },
        )
    ET.SubElement(
        root,
        "Relationship",
        {
            "Id": "rId4",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
            "Target": "styles.xml",
        },
    )
    return _xml_bytes(root)


def _root_rels_xml() -> bytes:
    root = ET.Element("Relationships", xmlns=_PACKAGE_REL_NS)
    ET.SubElement(
        root,
        "Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    return _xml_bytes(root)


def _content_types_xml() -> bytes:
    root = ET.Element("Types", xmlns=_CONTENT_NS)
    ET.SubElement(root, "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(root, "Default", {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(
        root,
        "Override",
        {"PartName": "/xl/workbook.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"},
    )
    ET.SubElement(
        root,
        "Override",
        {"PartName": "/xl/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"},
    )
    for index in range(1, 4):
        ET.SubElement(
            root,
            "Override",
            {
                "PartName": f"/xl/worksheets/sheet{index}.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
            },
        )
    return _xml_bytes(root)


def portfolio_to_xlsx_bytes(reports: list[ComplianceReport]) -> bytes:
    """Render a deterministic, formula-free three-sheet XLSX technical tabulation."""
    ranked = rank_reports(reports)
    if not ranked:
        raise ValueError("portfolio report requires at least one vendor report")
    if any(report.specification != ranked[0].specification for report in ranked):
        raise ValueError("all vendor reports must use the same specification")

    requirements = _requirements(ranked)
    if 4 + len(requirements) > _MAX_ROWS:
        raise ValueError("too many requirements for XLSX matrix")

    parts = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _root_rels_xml(),
        "xl/workbook.xml": _workbook_xml(),
        "xl/_rels/workbook.xml.rels": _workbook_rels_xml(),
        "xl/styles.xml": _styles_xml(),
        "xl/worksheets/sheet1.xml": _ranking_sheet(ranked),
        "xl/worksheets/sheet2.xml": _matrix_sheet(ranked, requirements),
        "xl/worksheets/sheet3.xml": _audit_sheet(ranked),
    }

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, parts[name])
    return buffer.getvalue()


def write_portfolio_xlsx(reports: list[ComplianceReport], path: str | Path) -> None:
    output = Path(path)
    if output.suffix.lower() != ".xlsx":
        raise ValueError("XLSX output path must end in .xlsx")
    output.write_bytes(portfolio_to_xlsx_bytes(reports))
