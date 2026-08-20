# Changelog

## Unreleased

### Added

- optional IfcOpenShell integration through a separate `ifc` package extra
- deterministic IFC vendor-property extraction into the existing `VendorFact` model
- explicit IFC element scoping with `--ifc-class` / `--ifc-guid` and optional `--ifc-pset`
- PDF-or-IFC vendor input dispatch for CLI `extract`, `compare` and `rank`
- IFC provenance encoded as `IfcClass:GlobalId/Pset` in the existing source section field
- regression coverage for scalar property extraction, scope ambiguity, provenance and PDF-to-IFC comparison
- IFC input reference documentation

### Changed

- development version advanced to `0.5.0.dev0`
- IFC class selection is rejected when it matches multiple elements; callers must use `--ifc-guid` instead of mixing multiple occurrences into one vendor fact set
- scalar numeric IFC properties remain unitless unless the property value explicitly contains a unit string

## 0.4.0 — 2026-08-20

### Added

- optional MCP v2 integration through a separate `mcp` package extra
- local stdio MCP server exposing deterministic `extract`, `compare` and `explain` tools
- `bidlint-mcp` console entrypoint
- `BIDLINT_MCP_ROOT` filesystem sandbox for MCP document and alias access
- pollable `submit_extract` and `submit_compare` background document jobs
- `job_status`, `job_result` and cooperative `cancel_job` MCP tools
- atomically persisted local job records under `.bidlint/jobs`
- bounded MCP job worker pool configurable with `BIDLINT_MCP_JOB_WORKERS`
- explicit recovery behavior that marks interrupted queued/running jobs failed after restart
- regression coverage for MCP tool outputs, path traversal, symlink escapes, job persistence, cancellation and restart recovery
- MCP server reference documentation

### Changed

- MCP remains an optional integration; the base bidlint install keeps no MCP SDK dependency
- long-running jobs use bidlint lifecycle tools rather than claiming native MCP Tasks-extension support before the Python SDK exposes it

## 0.3.0 — 2026-08-20

### Added

- provider-neutral `StructuredExtractor` protocol for optional AI or external structured extraction
- explicit requirement and vendor-fact candidate contracts with provider confidence and source evidence
- page-local evidence validation before provider candidates can enter deterministic core models
- rejection reporting for low-confidence, invalid-provenance, wrong-kind and structurally inconsistent candidates
- `extract_with_provider()` integration helper with provider identity and requested-kind validation
- optional extraction architecture documentation without adding an AI SDK or network dependency

### Changed

- provider confidence is treated only as extraction confidence; deterministic parameter matching and compliance evaluation remain authoritative

## 0.2.2 — 2026-08-20

### Added

- supplementary positioned-text extraction for explicit vendor-table geometry
- coordinate-aligned recovery for sparse table rows whose intermediate cells are visually blank
- explicit axis-aligned PDF rectangle capture for conservatively identifying merged intermediate table cells
- safe recovery when merged geometry leaves parameter and offered cells as distinct boxes
- deterministic parsing for repeated side-by-side table groups when each group repeats explicit parameter/value headers
- regression coverage proving blank unit cells stay unitless, near-boundary fragments are rejected, merges touching parameter/offered are not guessed, and incomplete repeated groups are skipped

### Changed

- layout-mode parsing remains the primary path; coordinate and rectangle evidence are used only as conservative fallbacks inside recognized tables
- content inside a merged intermediate cell is ignored rather than assigned to a single semantic column
- when a single table header contains both `Item` and `Description`, the parameter column nearest the explicit offered/value header is preferred

## 0.2.1 — 2026-08-20

### Added

- layout-preserving PDF extraction for vendor datasheets using pypdf layout mode
- deterministic header-driven parsing for tables with explicit parameter, unit and offered-value columns
- conservative parsing for two numeric parameter/value pairs rendered side-by-side on one visual row
- regression coverage for table footers, unrelated multi-column metadata and end-to-end compliance evaluation
- deterministic reconstruction when a final offered-value cell wraps to the immediately following numeric line
- deterministic reconstruction for parameter labels split by an explicit trailing hyphen
- sanitized motor, pump and valve datasheet layout fixtures rendered into temporary PDFs during tests
- fixture coverage for multi-page source provenance, metadata noise, side-by-side fields and wrapped table continuations
- multi-vendor Markdown tabulation with deterministic ranking and requirement-by-vendor decision matrix
- `rank --top N` for compact terminal ranking while preserving complete exports
- deterministic voltage conversion for `mV`, `V` and `kV`
- deterministic current conversion for `mA`, `A` and `kA`
- deterministic frequency conversion for `Hz`, `kHz` and `MHz`
- deterministic apparent-power conversion for `VA`, `kVA` and `MVA` without treating them as real power
- broader pressure conversion including `mbar` and `psi`
- broader length conversion including `km`, `in` and `ft`
- deterministic mass and force conversion for `g`/`kg`/`t` and `N`/`kN`
- explicit affine temperature conversion for `°C`, `°F` and `K`
- conservative aliases for common electrical, mechanical and rotational-speed unit spellings

### Changed

- `rank --output` now supports Markdown (`.md` / `.markdown`) in addition to JSON, HTML and CSV
- ambiguous unrecognized 3+ column vendor rows are skipped instead of being flattened into false two-column facts
- unmarked wrapped labels and arbitrary missing table cells remain unsupported instead of being guessed
- `psig`, `psia`, `kW`/`kVA` and frequency/rotational-speed relationships remain deliberately non-equivalent without project context

## 0.2.0 — 2026-08-19

### Added

- deterministic engineering unit conversion for power (`W`, `kW`, `MW`)
- deterministic engineering unit conversion for pressure (`Pa`, `kPa`, `MPa`, `bar`)
- deterministic engineering unit conversion for length (`mm`, `cm`, `m`)
- deterministic engineering unit conversion for flow (`L/s`, `L/min`, `m³/s`, `m³/h`)
- explicit dimension-safety: incompatible or unknown unit pairs remain `REVIEW`
- missing unit evidence remains `REVIEW` rather than being silently assumed
- conversion-aware finding explanations such as `10000w (= 10kw)`
- engineering-unit reference and five-minute quickstart documentation
- deterministic vendor parsing for colon-delimited and two-column datasheet fields
- paired-line extraction for numeric fields and explicit `Parameter:` qualitative fields
- vendor parsing reference documenting supported layouts and deliberate limits
- conservative built-in engineering terminology packs for explicit nomenclature variants
- project- and vendor-specific terminology aliases through `--aliases FILE.json`
- terminology reference documenting deliberate non-equivalences and matching order
- multi-vendor HTML technical bid tabulation with ranking summary and requirement-by-vendor matrix
- long-form CSV audit export for multi-vendor technical comparisons
- deterministic batch ranking tie-break order shared by terminal and portfolio outputs
- batch comparison reference documenting technical-only ranking semantics

### Changed

- descriptive values such as `316L stainless steel` remain qualitative instead of being interpreted as a numeric value
- ambiguous `protection class` is no longer treated as equivalent to an IP rating
- `rank --output` now supports `.json`, `.html` and `.csv`

## 0.1.0 — 2026-08-19

Initial deterministic compliance engine.

- page-preserving PDF extraction
- normative requirement detection
- numeric comparator parsing
- vendor key/value extraction
- deterministic parameter matching
- PASS / DEVIATION / MISSING / REVIEW findings
- JSON, Markdown, CSV and self-contained HTML output
- multi-vendor technical compliance ranking
- CLI and test suite
- CI matrix for Python 3.11, 3.12 and 3.13
- Dependabot configuration for Python and GitHub Actions dependencies
