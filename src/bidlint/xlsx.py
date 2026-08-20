from __future__ import annotations

import math
import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from . import __version__
from .models import ComplianceReport, Requirement, Status
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
    if not 1 <= index <= _MAX_COLS:
        raise ValueError("workbook column limit exceeded")
    parts: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        parts.append(chr(65 + remainder))
    return "".join(reversed(parts))


def _cell(reference: str, value: object, style: int) -> ET.Element:
    attrs = {"r": reference, "s": str(style)}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"non-finite workbook value at {reference}")
        cell = ET.Element(_q("c"), attrs)
        ET.SubElement(cell, _q("v")).text = f"{numeric:g}"
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
    styles: list[int],
    *,
    height: float | None = None,
) -> None:
    if row_number > _MAX_ROWS:
        raise ValueError("workbook row limit exceeded")
    attrs = {"r": str(row_number)}
    if height is not None:
        attrs.update({"ht": f"{height:g}", "customHeight": "1"})
    row = ET.SubElement(sheet_data, _q("row"), attrs)
    for column, value in enumerate(values, start=1):
        style = styles[column - 1] if column <= len(styles) else 4
        row.append(_cell(f"{_column_name(column)}{row_number}", value, style))


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


def _status_style(status: Status) -> int:
    return {
        Status.PASS: 7,
        Status.DEVIATION: 8,
        Status.MISSING: 9,
        Status.REVIEW: 10,
    }[status]


def _new_sheet(*, freeze_rows: int, freeze_columns: int = 0, widths: list[float]) -> tuple[ET.Element, ET.Element]:
    root = ET.Element(_q("worksheet"))
    views = ET.SubElement(root, _q("sheetViews"))
    view = ET.SubElement(views, _q("sheetView"), {"workbookViewId": "0"})
    if freeze_rows or freeze_columns:
        pane: dict[str, str] = {"state": "frozen"}
        if freeze_rows:
            pane["ySplit"] = str(freeze_rows)
        if freeze_columns:
            pane["xSplit"] = str(freeze_columns)
        pane["topLeftCell"] = f"{_column_name(freeze_columns + 1)}{freeze_rows + 1}"
        pane["activePane"] = "bottomRight" if freeze_rows and freeze_columns else (
            "bottomLeft" if freeze_rows else "topRight"
        )
        ET.SubElement(view, _q("pane"), pane)

    ET.SubElement(root, _q("sheetFormatPr"), {"defaultRowHeight": "15"})
    cols = ET.SubElement(root, _q("cols"))
    for index, width in enumerate(widths, start=1):
        ET.SubElement(
            cols,
            _q("col"),
            {"min": str(index), "max": str(index), "width": f"{width:g}", "customWidth": "1"},
        )
    return root, ET.SubElement(root, _q("sheetData"))


def _finish_sheet(root: ET.Element, *, auto_filter: str, merges: list[str]) -> None:
    # OOXML worksheet order requires autoFilter before mergeCells.
    ET.SubElement(root, _q("autoFilter"), {"ref": auto_filter})
    if merges:
        merge_cells = ET.SubElement(root, _q("mergeCells"), {"count": str(len(merges))})
        for reference in merges:
            ET.SubElement(merge_cells, _q("mergeCell"), {"ref": reference})
    ET.SubElement(
        root,
        _q("pageMargins"),
        {"left": "0.5", "right": "0.5", "top": "0.6", "bottom": "0.6", "header": "0.3", "footer": "0.3"},
    )


def _ranking_sheet(ranked: list[ComplianceReport]) -> bytes:
    root, data = _new_sheet(freeze_rows=4, widths=[8, 34, 14, 11, 13, 11, 11])
    _append_row(data, 1, ["bidlint technical bid tabulation"], [1], height=28)
    _append_row(data, 2, ["Specification", ranked[0].specification], [2, 4])
    _append_row(data, 3, ["Generated by", f"bidlint v{__version__}"], [2, 4])
    headers = ["Rank", "Vendor", "Score", "PASS", "DEVIATION", "MISSING", "REVIEW"]
    _append_row(data, 4, headers, [3] * len(headers), height=22)

    for rank, report in enumerate(ranked, start=1):
        counts = report.counts
        _append_row(
            data,
            4 + rank,
            [rank, report.vendor, report.compliance_score, counts["PASS"], counts["DEVIATION"], counts["MISSING"], counts["REVIEW"]],
            [6, 4, 5, 6, 6, 6, 6],
        )

    note_row = 6 + len(ranked)
    _append_row(
        data,
        note_row,
        ["Technical ranking only. Commercial price, delivery, payment terms and final engineering acceptance are outside bidlint."],
        [11],
        height=30,
    )
    _finish_sheet(
        root,
        auto_filter=f"A4:G{4 + len(ranked)}",
        merges=["A1:G1", f"A{note_row}:G{note_row}"],
    )
    return _xml_bytes(root)


def _matrix_sheet(ranked: list[ComplianceReport], requirements: list[Requirement]) -> bytes:
    column_count = 3 + len(ranked)
    if column_count > _MAX_COLS:
        raise ValueError("too many vendors for XLSX matrix")
    last_column = _column_name(column_count)
    root, data = _new_sheet(
        freeze_rows=4,
        freeze_columns=3,
        widths=[14, 28, 18] + [36] * len(ranked),
    )
    _append_row(data, 1, ["requirement-by-vendor matrix"], [1], height=28)
    _append_row(data, 2, ["Specification", ranked[0].specification], [2, 4])
    _append_row(data, 3, ["Cell format", "STATUS / offered value / deterministic reason"], [2, 11], height=28)
    headers = ["Requirement", "Parameter", "Required", *[report.vendor for report in ranked]]
    _append_row(data, 4, headers, [3] * len(headers), height=34)

    vendor_maps = [{finding.requirement.id: finding for finding in report.findings} for report in ranked]
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
            styles.append(_status_style(finding.status))
        _append_row(data, 4 + offset, values, styles, height=54)

    _finish_sheet(
        root,
        auto_filter=f"A4:{last_column}{4 + len(requirements)}",
        merges=[f"A1:{last_column}1"],
    )
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
    finding_count = sum(len(report.findings) for report in ranked)
    if 4 + finding_count > _MAX_ROWS:
        raise ValueError("too many findings for XLSX audit sheet")
    last_column = _column_name(len(headers))
    root, data = _new_sheet(
        freeze_rows=4,
        widths=[8, 30, 12, 14, 16, 28, 18, 24, 13, 12, 26, 12, 28, 54],
    )
    _append_row(data, 1, ["technical compliance audit"], [1], height=28)
    _append_row(data, 2, ["Specification", ranked[0].specification], [2, 4])
    _append_row(data, 3, ["Generated by", f"bidlint v{__version__}"], [2, 4])
    _append_row(data, 4, headers, [3] * len(headers), height=28)

    row = 5
    for rank, report in enumerate(ranked, start=1):
        for finding in report.findings:
            requirement = finding.requirement
            fact = finding.vendor_fact
            spec_source = requirement.source
            vendor_source = fact.source if fact else None
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
                [6, 4, 5, _status_style(finding.status), 4, 4, 4, 4, 12, 6, 11, 6, 11, 11],
                height=34,
            )
            row += 1

    _finish_sheet(
        root,
        auto_filter=f"A4:{last_column}{row - 1}",
        merges=[f"A1:{last_column}1"],
    )
    return _xml_bytes(root)


def _styles_xml() -> bytes:
    root = ET.Element(_q("styleSheet"))
    num_fmts = ET.SubElement(root, _q("numFmts"), {"count": "2"})
    ET.SubElement(num_fmts, _q("numFmt"), {"numFmtId": "164", "formatCode": '0.0"%"'})
    ET.SubElement(num_fmts, _q("numFmt"), {"numFmtId": "165", "formatCode": "0.000"})

    fonts = ET.SubElement(root, _q("fonts"), {"count": "3"})
    default_font = ET.SubElement(fonts, _q("font"))
    ET.SubElement(default_font, _q("sz"), {"val": "11"})
    ET.SubElement(default_font, _q("name"), {"val": "Calibri"})
    ET.SubElement(default_font, _q("family"), {"val": "2"})
    title_font = ET.SubElement(fonts, _q("font"))
    ET.SubElement(title_font, _q("b"))
    ET.SubElement(title_font, _q("sz"), {"val": "18"})
    ET.SubElement(title_font, _q("color"), {"rgb": "FFFFFFFF"})
    ET.SubElement(title_font, _q("name"), {"val": "Calibri"})
    header_font = ET.SubElement(fonts, _q("font"))
    ET.SubElement(header_font, _q("b"))
    ET.SubElement(header_font, _q("sz"), {"val": "11"})
    ET.SubElement(header_font, _q("color"), {"rgb": "FFFFFFFF"})
    ET.SubElement(header_font, _q("name"), {"val": "Calibri"})

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
        item = ET.SubElement(border, _q(edge), {"style": "thin"})
        ET.SubElement(item, _q("color"), {"rgb": "FFE2E8F0"})
    ET.SubElement(border, _q("diagonal"))

    style_xfs = ET.SubElement(root, _q("cellStyleXfs"), {"count": "1"})
    ET.SubElement(style_xfs, _q("xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"})
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
            alignment: dict[str, str] = {}
            if horizontal:
                alignment["horizontal"] = horizontal
            if vertical:
                alignment["vertical"] = vertical
            if wrap:
                alignment["wrapText"] = "1"
            ET.SubElement(xf, _q("alignment"), alignment)
            xf.set("applyAlignment", "1")

    add_xf()
    add_xf(font_id=1, fill_id=2, vertical="center")
    add_xf(font_id=2, vertical="center")
    add_xf(font_id=2, fill_id=3, border_id=1, horizontal="center", vertical="center", wrap=True)
    add_xf(border_id=1, vertical="top")
    add_xf(num_fmt=164, border_id=1, horizontal="right", vertical="top")
    add_xf(border_id=1, horizontal="right", vertical="top")
    add_xf(fill_id=4, border_id=1, vertical="top", wrap=True)
    add_xf(fill_id=5, border_id=1, vertical="top", wrap=True)
    add_xf(fill_id=6, border_id=1, vertical="top", wrap=True)
    add_xf(fill_id=7, border_id=1, vertical="top", wrap=True)
    add_xf(border_id=1, vertical="top", wrap=True)
    add_xf(num_fmt=165, border_id=1, horizontal="right", vertical="top")

    cell_styles = ET.SubElement(root, _q("cellStyles"), {"count": "1"})
    ET.SubElement(cell_styles, _q("cellStyle"), {"name": "Normal", "xfId": "0", "builtinId": "0"})
    ET.SubElement(root, _q("dxfs"), {"count": "0"})
    ET.SubElement(
        root,
        _q("tableStyles"),
        {"count": "0", "defaultTableStyle": "TableStyleMedium2", "defaultPivotStyle": "PivotStyleLight16"},
    )
    return _xml_bytes(root)


def _workbook_xml() -> bytes:
    root = ET.Element(_q("workbook"))
    ET.SubElement(root, _q("workbookPr"))
    views = ET.SubElement(root, _q("bookViews"))
    ET.SubElement(views, _q("workbookView"), {"windowWidth": "24000", "windowHeight": "12000"})
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
