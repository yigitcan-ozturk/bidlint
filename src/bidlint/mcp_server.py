from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from .compare import compare
from .parse import parse_requirements, parse_vendor_facts
from .terminology import load_alias_file

mcp = MCPServer("bidlint")


def _server_root() -> Path:
    configured = os.environ.get("BIDLINT_MCP_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path.cwd().resolve()


def _resolve_local_file(path: str, *, suffix: str) -> Path:
    root = _server_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path must stay within MCP root {root}")
    if not resolved.is_file():
        raise ValueError(f"file does not exist: {path}")
    if resolved.suffix.lower() != suffix:
        raise ValueError(f"expected a {suffix} file: {path}")
    return resolved


def _validate_threshold(threshold: float) -> float:
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("threshold must be a number between 0 and 1")
    threshold = float(threshold)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    return threshold


def _load_aliases(path: str | None):
    if path is None:
        return None
    alias_path = _resolve_local_file(path, suffix=".json")
    return load_alias_file(alias_path)


def extract_document(document: str, kind: Literal["specification", "vendor"]) -> dict:
    """Extract deterministic requirements or vendor facts from a local PDF."""
    pdf = _resolve_local_file(document, suffix=".pdf")
    if kind == "specification":
        items = parse_requirements(pdf)
    elif kind == "vendor":
        items = parse_vendor_facts(pdf)
    else:  # defensive for direct Python callers; MCP schema constrains this.
        raise ValueError("kind must be 'specification' or 'vendor'")
    return {
        "document": pdf.name,
        "kind": kind,
        "count": len(items),
        "items": [asdict(item) for item in items],
    }


def compare_documents(
    specification: str,
    vendor: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Compare one local specification PDF with one local vendor PDF."""
    spec_path = _resolve_local_file(specification, suffix=".pdf")
    vendor_path = _resolve_local_file(vendor, suffix=".pdf")
    threshold = _validate_threshold(threshold)
    requirements = parse_requirements(spec_path)
    facts = parse_vendor_facts(vendor_path)
    report = compare(
        requirements,
        facts,
        spec_path.name,
        vendor_path.name,
        threshold=threshold,
        aliases=_load_aliases(aliases),
    )
    return report.to_dict()


def explain_requirement(
    specification: str,
    vendor: str,
    requirement_id: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Explain one deterministic finding, including its source evidence."""
    if not isinstance(requirement_id, str) or not requirement_id.strip():
        raise ValueError("requirement_id is required")
    report = compare_documents(specification, vendor, threshold=threshold, aliases=aliases)
    wanted = requirement_id.strip().casefold()
    for finding in report["findings"]:
        if finding["requirement"]["id"].casefold() == wanted:
            return {
                "specification": report["specification"],
                "vendor": report["vendor"],
                "finding": finding,
            }
    raise ValueError(f"requirement not found: {requirement_id}")


@mcp.tool(name="extract")
def extract_tool(document: str, kind: Literal["specification", "vendor"]) -> dict:
    """Extract source-traceable requirements or vendor facts from a local PDF."""
    return extract_document(document, kind)


@mcp.tool(name="compare")
def compare_tool(
    specification: str,
    vendor: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Run deterministic technical compliance comparison for one vendor."""
    return compare_documents(specification, vendor, threshold=threshold, aliases=aliases)


@mcp.tool(name="explain")
def explain_tool(
    specification: str,
    vendor: str,
    requirement_id: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Return the deterministic reason and evidence for one requirement finding."""
    return explain_requirement(
        specification,
        vendor,
        requirement_id,
        threshold=threshold,
        aliases=aliases,
    )


def main() -> None:
    """Run the local MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
