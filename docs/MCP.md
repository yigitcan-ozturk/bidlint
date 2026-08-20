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

## Synchronous tools

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

## Long-running local jobs

For large PDFs or comparisons that should not hold one tool call open, v0.4 adds a local pollable job lifecycle.

### `submit_extract`

Queues deterministic extraction and immediately returns a job handle.

### `submit_compare`

Queues deterministic comparison and immediately returns a job handle.

### `job_status`

Polls lifecycle metadata without returning the potentially large result payload.

Statuses are:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

### `job_result`

Returns job metadata plus:

- `result` for a completed job
- `error` for a failed job
- neither while work is still queued/running

### `cancel_job`

Requests cooperative cancellation. A queued job can normally be cancelled before it begins. A running PDF parse/evaluation is not force-killed; the cancellation request is recorded and its completed work is discarded instead of being published as a result.

## Job persistence

Job records are stored under:

```text
<BIDLINT_MCP_ROOT>/.bidlint/jobs/<job-id>.json
```

Writes are atomic so polling does not observe partially written JSON.

Terminal job results remain readable from the same root after a server restart. Work that was `queued` or `running` when the process stopped is **not** silently resumed; on the next server start it is marked `failed` with an explicit restart error.

The worker pool is bounded. The default is two active jobs. It can be configured from 1 to 8 workers:

```bash
export BIDLINT_MCP_JOB_WORKERS=4
```

Job records store paths relative to the MCP root instead of exposing absolute local filesystem paths.

## MCP Tasks extension boundary

The MCP 2026-07-28 protocol defines the `io.modelcontextprotocol/tasks` extension for native asynchronous task handles. The official Python SDK v2 line used by this release does not yet expose that extension as a supported server API.

For that reason, bidlint v0.4 implements explicit `submit_* / job_status / job_result / cancel_job` tools rather than claiming native MCP Tasks support. The internal job state machine is deliberately separate so it can be adapted to the standard Tasks extension when the SDK exposes that surface.

## Safety boundary

The MCP server does not create a second evaluation engine.

```text
MCP host
   │
   ├── extract / compare / explain
   │
   └── submit_* -> local job state -> job_status / job_result
                    │
                    ▼
        existing bidlint parsers + matcher + unit evaluator
                    │
                    ▼
        PASS / DEVIATION / MISSING / REVIEW
```

An MCP client cannot supply a compliance status and have bidlint trust it. Both synchronous and queued paths compute results through the same deterministic core used by the CLI.

The optional AI extraction boundary introduced in v0.3 remains separate. If an external extraction provider is used elsewhere, its candidates still require confidence and provenance validation before they can enter the deterministic evaluation layer.

## Current limits

- local text-based PDFs only
- no URL fetching
- no OCR
- stdio transport in the initial v0.4 server
- active jobs use an in-process bounded worker pool
- running work is cooperatively cancelled, not force-terminated
- in-progress jobs are not resumed after a process restart
- native MCP Tasks-extension support waits for an SDK surface instead of being emulated at the wire-protocol level
