from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

_BUILTIN_CURRENCY_NUMFMT_IDS = {5, 6, 7, 8}
_CURRENCY_FORMAT = re.compile(
    r"(?:£|€|¥|₺|\b(?:GBP|USD|EUR|TRY)\b|\[\$\$-[0-9A-F]+\]|\$(?!-))",
    re.IGNORECASE,
)


def _currency_num_fmt_ids(styles_root: ET.Element) -> set[int]:
    ids = set(_BUILTIN_CURRENCY_NUMFMT_IDS)
    for item in styles_root.findall(".//{*}numFmt"):
        raw_id = item.attrib.get("numFmtId")
        code = item.attrib.get("formatCode", "")
        try:
            num_fmt_id = int(raw_id) if raw_id is not None else None
        except ValueError:
            continue
        if num_fmt_id is not None and _CURRENCY_FORMAT.search(code):
            ids.add(num_fmt_id)
    return ids


def _currency_style_indexes(styles_root: ET.Element) -> set[int]:
    currency_num_fmts = _currency_num_fmt_ids(styles_root)
    cell_xfs = styles_root.find(".//{*}cellXfs")
    if cell_xfs is None:
        return set()

    indexes: set[int] = set()
    for index, xf in enumerate(list(cell_xfs)):
        raw_id = xf.attrib.get("numFmtId", "0")
        try:
            num_fmt_id = int(raw_id)
        except ValueError:
            continue
        if num_fmt_id in currency_num_fmts:
            indexes.add(index)
    return indexes


def currency_formatted_cell_count(archive: zipfile.ZipFile) -> int:
    """Count numeric worksheet cells that actively use a currency number format.

    The count is deliberately content-free: no worksheet names, cell references,
    format strings, or numeric values are returned to sanitization evidence.
    """
    if "xl/styles.xml" not in archive.namelist():
        return 0
    try:
        styles_root = ET.fromstring(archive.read("xl/styles.xml"))
    except (ET.ParseError, KeyError) as exc:
        raise ValueError("invalid XLSX styles.xml") from exc

    currency_styles = _currency_style_indexes(styles_root)
    if not currency_styles:
        return 0

    count = 0
    for name in archive.namelist():
        lowered = name.casefold()
        if not lowered.startswith("xl/worksheets/") or not lowered.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(archive.read(name))
        except (ET.ParseError, KeyError) as exc:
            raise ValueError("invalid XLSX worksheet XML while checking currency formats") from exc
        for cell in root.findall(".//{*}c"):
            raw_style = cell.attrib.get("s")
            if raw_style is None:
                continue
            try:
                style_index = int(raw_style)
            except ValueError:
                continue
            if style_index not in currency_styles:
                continue
            cell_type = cell.attrib.get("t", "n")
            if cell_type not in {"n", ""}:
                continue
            value = cell.find("{*}v")
            if value is not None and value.text and value.text.strip():
                count += 1
    return count
