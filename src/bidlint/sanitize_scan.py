from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .errors import ExitCode
from .pilot import PilotManifest, build_parser as build_pilot_parser, load_manifest, main as unguarded_pilot_main
from .xlsx_format_scan import currency_formatted_cell_count


@dataclass(frozen=True, slots=True)
class SanitizationFinding:
    severity: str
    category: str
    file: str
    location: str
    count: int
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "location": self.location,
            "count": self.count,
            "message": self.message,
        }


_BLOCK_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "email-address",
        re.compile(r"(?i)(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])"),
        "email-like contact data detected",
    ),
    (
        "phone-number",
        re.compile(r"(?<!\w)\+\d(?:[\s().-]*\d){7,14}(?!\d)"),
        "international phone-like contact data detected",
    ),
    (
        "commercial-money",
        re.compile(r"(?i)(?:EUR|USD|GBP|TRY|€|£|\$)\s*[0-9][0-9.,]*|[0-9][0-9.,]*\s*(?:EUR|USD|GBP|TRY)\b"),
        "currency amount detected; commercial values must be removed or neutralized",
    ),
    (
        "commercial-terms",
        re.compile(
            r"(?i)\b(?:unit\s+(?:price|rate|cost)|line\s+total|subtotal|extended\s+(?:price|cost|amount)|"
            r"total\s+(?:price|cost|amount)|currency|payment\s+terms?|offer\s+validity|incoterms?|"
            r"EXW|FOB|FCA|CIF|CIP|DAP|DPU|DDP)\b"
        ),
        "commercial or contractual term detected",
    ),
    (
        "legal-entity-name",
        re.compile(
            r"(?i)\b[A-Z][A-Z0-9&.'’() -]{2,80}\s+(?:LTD|LIMITED|LLC|GMBH|INC\.?|PLC|A\.S\.|AŞ|S\.A\.)\b"
        ),
        "legal-entity-like name detected",
    ),
    (
        "tax-identifier-label",
        re.compile(r"(?i)\b(?:VAT\s*(?:NO\.?|NUMBER)?|TAX\s*(?:ID|NUMBER)|VKN)\b"),
        "tax-identifier label detected",
    ),
)

_REVIEW_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "url",
        re.compile(r"(?i)\bhttps?://[^\s<>\]\[()]+|\bwww\.[^\s<>\]\[()]+"),
        "URL detected; confirm it is intentionally public and non-sensitive",
    ),
    (
        "identity-label",
        re.compile(r"(?i)\b(?:buyer|seller|attention|attn\.?|address|signature|company\s+stamp|prepared\s+for)\b"),
        "identity/address/signature label detected; inspect the surrounding source manually",
    ),
)

_TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv", ".ifc", ".xml"}
_OOXML_SUFFIXES = {".xlsx", ".docx"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
_BENIGN_PDF_METADATA = {"anonymous", "untitled", "none", ""}
_IGNORED_PDF_METADATA_KEYS = {"/Producer", "/Creator", "/CreationDate", "/ModDate", "/Trapped"}

_OOXML_STRUCTURAL_URL = re.compile(
    r"(?i)https?://(?:schemas\.openxmlformats\.org|schemas\.microsoft\.com|purl\.org/dc|"
    r"www\.w3\.org/(?:2000|2001|XML))/[^\s\"'<>]*"
)


def _finding(
    severity: str,
    category: str,
    file: str,
    location: str,
    count: int,
    message: str,
) -> SanitizationFinding:
    return SanitizationFinding(severity, category, file, location, count, message)


def _scan_text(text: str, *, file: str, location: str) -> list[SanitizationFinding]:
    findings: list[SanitizationFinding] = []
    for category, pattern, message in _BLOCK_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            findings.append(_finding("BLOCK", category, file, location, count, message))
    for category, pattern, message in _REVIEW_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            findings.append(_finding("REVIEW", category, file, location, count, message))
    return findings


def _scan_ooxml_text(text: str, *, file: str, location: str) -> list[SanitizationFinding]:
    """Ignore package-schema URLs while retaining URLs in actual OOXML content."""
    return _scan_text(_OOXML_STRUCTURAL_URL.sub("", text), file=file, location=location)


def _scan_pdf(path: Path, display: str) -> list[SanitizationFinding]:
    try:
        reader = PdfReader(str(path))
    except (OSError, PdfReadError, ValueError) as exc:
        raise ValueError(f"unable to inspect PDF {display}: {exc}") from exc

    findings: list[SanitizationFinding] = []
    metadata = reader.metadata or {}
    sensitive_metadata = []
    for key, value in metadata.items():
        if key in _IGNORED_PDF_METADATA_KEYS or value is None:
            continue
        normalized = str(value).strip().casefold()
        if normalized not in _BENIGN_PDF_METADATA:
            sensitive_metadata.append(str(key))
    if sensitive_metadata:
        findings.append(
            _finding(
                "BLOCK",
                "pdf-metadata",
                display,
                "metadata",
                len(sensitive_metadata),
                "non-generic PDF metadata detected; strip project/author/title metadata before pilot use",
            )
        )

    attachments = getattr(reader, "attachments", None)
    if attachments:
        findings.append(
            _finding(
                "BLOCK",
                "pdf-embedded-files",
                display,
                "document",
                len(attachments),
                "embedded PDF attachments detected; inspect/remove them before pilot use",
            )
        )

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pypdf page content can fail independently of document parsing
            raise ValueError(f"unable to inspect PDF text {display} page {index}: {exc}") from exc
        findings.extend(_scan_text(text, file=display, location=f"page:{index}"))

    findings.append(
        _finding(
            "REVIEW",
            "pdf-visual-content-uninspected",
            display,
            "document",
            1,
            "PDF raster/vector visual content is not OCR-inspected; manually verify images, stamps, signatures and screenshots",
        )
    )
    return findings


def _decode_xml(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore")


def _scan_ooxml(path: Path, display: str) -> list[SanitizationFinding]:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"unable to inspect OOXML {display}: {exc}") from exc

    findings: list[SanitizationFinding] = []
    with archive:
        names = archive.namelist()
        comment_entries = [name for name in names if "comments" in name.casefold()]
        if comment_entries:
            findings.append(
                _finding(
                    "BLOCK",
                    "ooxml-comments",
                    display,
                    "archive",
                    len(comment_entries),
                    "OOXML comment content detected",
                )
            )
        external_entries = [name for name in names if "externallinks" in name.casefold()]
        if external_entries:
            findings.append(
                _finding(
                    "BLOCK",
                    "xlsx-external-links",
                    display,
                    "archive",
                    len(external_entries),
                    "external workbook links detected",
                )
            )
        media_entries = [name for name in names if "/media/" in name.casefold()]
        if media_entries:
            findings.append(
                _finding(
                    "REVIEW",
                    "ooxml-media-uninspected",
                    display,
                    "archive",
                    len(media_entries),
                    "embedded OOXML media is not OCR-inspected; verify images manually",
                )
            )

        for name in names:
            lowered = name.casefold()
            if not lowered.endswith((".xml", ".rels")):
                continue
            try:
                text = _decode_xml(archive.read(name))
            except KeyError:
                continue
            findings.extend(_scan_ooxml_text(text, file=display, location=name))

            if lowered.endswith("xl/workbook.xml"):
                hidden_count = len(re.findall(r'(?i)\bstate\s*=\s*["\'](?:hidden|veryHidden)["\']', text))
                if hidden_count:
                    findings.append(
                        _finding(
                            "BLOCK",
                            "xlsx-hidden-sheets",
                            display,
                            name,
                            hidden_count,
                            "hidden/veryHidden worksheets detected",
                        )
                    )
            if lowered.endswith("docprops/core.xml"):
                core_values = re.findall(r">\s*([^<>\s][^<>]*)\s*<", text)
                meaningful = [value for value in core_values if value.strip()]
                if meaningful:
                    findings.append(
                        _finding(
                            "BLOCK",
                            "ooxml-core-metadata",
                            display,
                            name,
                            len(meaningful),
                            "OOXML core metadata detected; strip author/title/project metadata before pilot use",
                        )
                    )

        if path.suffix.casefold() == ".xlsx":
            currency_cells = currency_formatted_cell_count(archive)
            if currency_cells:
                findings.append(
                    _finding(
                        "BLOCK",
                        "xlsx-currency-formatted-cells",
                        display,
                        "worksheets/styles",
                        currency_cells,
                        "currency-formatted numeric cells detected; remove commercial values before pilot use",
                    )
                )
    return findings


def _scan_plain(path: Path, display: str) -> list[SanitizationFinding]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise ValueError(f"unable to inspect text file {display}: {exc}") from exc
    return _scan_text(text, file=display, location="text")


def scan_file(path: str | Path, *, display: str | None = None) -> list[SanitizationFinding]:
    source = Path(path)
    shown = display or source.name
    findings = _scan_text(source.name, file=shown, location="filename")
    suffix = source.suffix.casefold()
    if suffix == ".pdf":
        findings.extend(_scan_pdf(source, shown))
    elif suffix in _OOXML_SUFFIXES:
        findings.extend(_scan_ooxml(source, shown))
    elif suffix in _TEXT_SUFFIXES:
        findings.extend(_scan_plain(source, shown))
    elif suffix in _IMAGE_SUFFIXES:
        findings.append(
            _finding(
                "REVIEW",
                "image-content-uninspected",
                shown,
                "file",
                1,
                "image content requires manual inspection; no OCR is performed by the sanitization scanner",
            )
        )
    else:
        findings.append(
            _finding(
                "REVIEW",
                "unsupported-content-uninspected",
                shown,
                "file",
                1,
                "file type is not content-inspected by the sanitization scanner",
            )
        )
    return findings


def _iter_root(label: str, root: Path) -> Iterable[tuple[Path, str]]:
    if root.is_file():
        yield root, f"{label}/{root.name}"
        return
    files = sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    )
    for child in files:
        yield child, f"{label}/{child.relative_to(root).as_posix()}"


def scan_manifest(manifest: PilotManifest, *, manifest_path: str | Path | None = None) -> dict[str, object]:
    roots: list[tuple[str, Path]] = [("specification", manifest.specification)]
    roots.extend((f"vendor[{index}]", vendor) for index, vendor in enumerate(manifest.vendors))
    if manifest.aliases is not None:
        roots.append(("aliases", manifest.aliases))
    if manifest.knockouts is not None:
        roots.append(("knockouts", manifest.knockouts))

    findings: list[SanitizationFinding] = []
    files_scanned = 0
    if manifest_path is not None:
        source = Path(manifest_path)
        findings.extend(scan_file(source, display="manifest.json"))
        files_scanned += 1

    for label, root in roots:
        for path, display in _iter_root(label, root):
            if path.is_symlink():
                findings.append(
                    _finding("BLOCK", "symlink", display, "file", 1, "symlinked corpus content is not allowed")
                )
                continue
            findings.extend(scan_file(path, display=display))
            files_scanned += 1

    findings.sort(key=lambda item: (item.severity, item.file, item.location, item.category))
    blockers = [item for item in findings if item.severity == "BLOCK"]
    reviews = [item for item in findings if item.severity == "REVIEW"]
    return {
        "tool": "bidlint-pilot-scan",
        "pilot_id": manifest.pilot_id,
        "automated_clear": not blockers,
        "manual_review_required": bool(reviews),
        "files_scanned": files_scanned,
        "blocker_count": len(blockers),
        "review_count": len(reviews),
        "findings": [item.to_dict() for item in findings],
        "limitations": [
            "The scanner does not OCR raster images or visually inspect drawings/screenshots.",
            "A clear automated scan is not a substitute for the manual sanitization checklist and domain review.",
            "Findings intentionally omit matched sensitive text so scan output does not become a secondary data leak.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidlint-pilot-scan",
        description="Conservatively scan a BidLint pilot corpus for sanitization blockers without echoing matched secrets.",
    )
    parser.add_argument("manifest", help="pilot manifest JSON")
    parser.add_argument("--json", action="store_true", dest="json_output", help="print machine-readable scan result")
    parser.add_argument("--output", metavar="FILE.json", help="write scan result JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.output and Path(args.output).suffix.casefold() != ".json":
        print("sanitization scan failed: --output must end in .json", file=sys.stderr)
        return int(ExitCode.CONFIG)
    try:
        manifest, _ = load_manifest(args.manifest)
        result = scan_manifest(manifest, manifest_path=args.manifest)
    except OSError as exc:
        print(f"unable to read pilot corpus: {exc}", file=sys.stderr)
        return int(ExitCode.IO)
    except ValueError as exc:
        print(f"sanitization scan failed: {exc}", file=sys.stderr)
        return int(ExitCode.INPUT)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        try:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"unable to write sanitization scan: {exc}", file=sys.stderr)
            return int(ExitCode.IO)
    if args.json_output:
        print(rendered)
    else:
        status = "CLEAR" if result["automated_clear"] else "BLOCKED"
        print(f"{status} — {manifest.pilot_id}")
        print(
            f"files: {result['files_scanned']}; blockers: {result['blocker_count']}; "
            f"manual review: {result['review_count']}"
        )
    return int(ExitCode.SUCCESS if result["automated_clear"] else ExitCode.INPUT)


def guarded_pilot_main(argv: list[str] | None = None) -> int:
    parsed = build_pilot_parser().parse_args(argv)
    try:
        manifest, _ = load_manifest(parsed.manifest)
        scan = scan_manifest(manifest, manifest_path=parsed.manifest)
    except OSError as exc:
        print(f"unable to read pilot corpus: {exc}", file=sys.stderr)
        return int(ExitCode.IO)
    except ValueError as exc:
        print(f"pilot sanitization scan failed: {exc}", file=sys.stderr)
        return int(ExitCode.INPUT)
    if scan["blocker_count"]:
        print(
            f"pilot validation failed: sanitization scan found {scan['blocker_count']} blocker(s); "
            "run bidlint-pilot-scan for the non-sensitive finding register",
            file=sys.stderr,
        )
        return int(ExitCode.INPUT)
    return unguarded_pilot_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
