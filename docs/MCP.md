# MCP server

`bidlint` can expose its deterministic technical-compliance core through a local Model Context Protocol (MCP) server.

The MCP integration is optional. A normal `pip install bidlint` does not install the MCP SDK.

## Install

```bash
pip install -e '.[mcp]'
```

For development, the `dev` extra also includes the MCP SDK.

## Run

```bash
bidlint-mcp
```

The server uses MCP stdio transport by default. It does not open a network port.

You can also run the module directly:

```bash
python -m bidlint.mcp_server
```

## File-access root

MCP tools accept local file paths. To avoid giving an MCP host arbitrary filesystem access, bidlint constrains all document and alias paths to one root directory.

By default, that root is the server process working directory.

Set an explicit root with:

```bash
export BIDLINT_MCP_ROOT=/path/to/project/documents
bidlint-mcp
```

Windows PowerShell:

```powershell
$env:BIDLINT_MCP_ROOT = 'C:\path\to\project\documents'
bidlint-mcp
```

Relative paths are resolved under that root. Absolute paths are accepted only when they remain inside the same root. Parent traversal and symlinks that resolve outside the root are rejected.

The server does not fetch URLs or remote documents.

## Tools

### `extract`

Extract deterministic requirements or vendor facts from a local text-based PDF.

Inputs:

- `document`: local PDF path under the MCP root
- `kind`: `specification` or `vendor`

The output includes normalized items and source page/line provenance.

### `compare`

Compare one local specification PDF with one local vendor PDF using the existing deterministic bidlint evaluator.

Inputs:

- `specification`
- `vendor`
- `threshold` (optional, default `0.52`)
- `aliases` (optional local JSON terminology-alias file)

The result is the same compliance data contract used by the CLI: score, counts and `PASS / DEVIATION / MISSING / REVIEW` findings.

### `explain`

Return one finding from a deterministic comparison by requirement ID.

Inputs:

- `specification`
- `vendor`
- `requirement_id`, for example `R0001`
- `threshold` (optional)
- `aliases` (optional)

The response keeps the requirement, matched vendor evidence, status, confidence and deterministic reason together.

## Safety boundary

The MCP server does not create a second evaluation engine.

```text
MCP host
   │
   ▼
extract / compare / explain
   │
   ▼
existing bidlint parsers + matcher + unit evaluator
   │
   ▼
PASS / DEVIATION / MISSING / REVIEW
```

An MCP client cannot supply a compliance status and have bidlint trust it. The server computes results through the same deterministic core used by the CLI.

The optional AI extraction boundary introduced in v0.3 remains separate. If an external extraction provider is used elsewhere, its candidates still require confidence and provenance validation before they can enter the deterministic evaluation layer.

## Current limits

- local text-based PDFs only
- no URL fetching
- no OCR
- stdio transport only in the initial v0.4 server milestone
- each tool call is synchronous in this milestone
- long-running document jobs are a separate v0.4 roadmap item
