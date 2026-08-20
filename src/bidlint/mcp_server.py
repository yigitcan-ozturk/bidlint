from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from .compare import compare
from .jobs import get_job_manager
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


def _relative_to_root(path: Path) -> str:
    return path.resolve().relative_to(_server_root()).as_posix()


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


def _extract_resolved(pdf: Path, kind: Literal["specification", "vendor"]) -> dict:
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


def extract_document(document: str, kind: Literal["specification", "vendor"]) -> dict:
    """Extract deterministic requirements or vendor facts from a local PDF."""
    return _extract_resolved(_resolve_local_file(document, suffix=".pdf"), kind)


def _compare_resolved(
    specification: Path,
    vendor: Path,
    *,
    threshold: float,
    aliases,
) -> dict:
    requirements = parse_requirements(specification)
    facts = parse_vendor_facts(vendor)
    report = compare(
        requirements,
        facts,
        specification.name,
        vendor.name,
        threshold=threshold,
        aliases=aliases,
    )
    return report.to_dict()


def compare_documents(
    specification: str,
    vendor: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Compare one local specification PDF with one local vendor PDF."""
    spec_path = _resolve_local_file(specification, suffix=".pdf")
    vendor_path = _resolve_local_file(vendor, suffix=".pdf")
    return _compare_resolved(
        spec_path,
        vendor_path,
        threshold=_validate_threshold(threshold),
        aliases=_load_aliases(aliases),
    )


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


def submit_extract_job(document: str, kind: Literal["specification", "vendor"]) -> dict:
    """Queue deterministic extraction and return a pollable local job handle."""
    pdf = _resolve_local_file(document, suffix=".pdf")
    request = {"document": _relative_to_root(pdf), "kind": kind}
    manager = get_job_manager(_server_root())
    return manager.submit(
        operation="extract",
        request=request,
        runner=lambda: _extract_resolved(pdf, kind),
    )


def submit_compare_job(
    specification: str,
    vendor: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Queue deterministic comparison and return a pollable local job handle."""
    spec_path = _resolve_local_file(specification, suffix=".pdf")
    vendor_path = _resolve_local_file(vendor, suffix=".pdf")
    threshold = _validate_threshold(threshold)
    alias_map = _load_aliases(aliases)
    request = {
        "specification": _relative_to_root(spec_path),
        "vendor": _relative_to_root(vendor_path),
        "threshold": threshold,
        "aliases": _relative_to_root(_resolve_local_file(aliases, suffix=".json")) if aliases else None,
    }
    manager = get_job_manager(_server_root())
    return manager.submit(
        operation="compare",
        request=request,
        runner=lambda: _compare_resolved(
            spec_path,
            vendor_path,
            threshold=threshold,
            aliases=alias_map,
        ),
    )


def get_job_status(job_id: str) -> dict:
    """Return current local job lifecycle state without the result payload."""
    return get_job_manager(_server_root()).status(job_id)


def get_job_result(job_id: str) -> dict:
    """Return current job state plus result/error when terminal."""
    return get_job_manager(_server_root()).result(job_id)


def cancel_document_job(job_id: str) -> dict:
    """Request cooperative cancellation for a queued or running local job."""
    return get_job_manager(_server_root()).cancel(job_id)


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


@mcp.tool(name="submit_extract")
def submit_extract_tool(document: str, kind: Literal["specification", "vendor"]) -> dict:
    """Start extraction as a background local job and return its job ID."""
    return submit_extract_job(document, kind)


@mcp.tool(name="submit_compare")
def submit_compare_tool(
    specification: str,
    vendor: str,
    threshold: float = 0.52,
    aliases: str | None = None,
) -> dict:
    """Start comparison as a background local job and return its job ID."""
    return submit_compare_job(specification, vendor, threshold=threshold, aliases=aliases)


@mcp.tool(name="job_status")
def job_status_tool(job_id: str) -> dict:
    """Poll the lifecycle state of a local bidlint document job."""
    return get_job_status(job_id)


@mcp.tool(name="job_result")
def job_result_tool(job_id: str) -> dict:
    """Retrieve the result or error for a local bidlint document job."""
    return get_job_result(job_id)


@mcp.tool(name="cancel_job")
def cancel_job_tool(job_id: str) -> dict:
    """Request cooperative cancellation of a local bidlint document job."""
    return cancel_document_job(job_id)


def main() -> None:
    """Run the local MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
