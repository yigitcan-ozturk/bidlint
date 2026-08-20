# Roadmap

## v0.1 — deterministic core
- [x] PDF text extraction with page provenance
- [x] requirement extraction
- [x] vendor fact extraction
- [x] PASS / DEVIATION / MISSING / REVIEW
- [x] JSON / CSV / Markdown outputs
- [x] CI on Python 3.11–3.13

## v0.2.0 — real-world engineering workflow
- [x] deterministic unit conversion for core power, pressure, length and flow units
- [x] deterministic colon, two-column and paired-line vendor field extraction
- [x] conservative engineering terminology packs and project-specific JSON aliases
- [x] batch vendor ranking with HTML matrix and CSV audit exports
- [x] explicit uncertainty rules for missing, incompatible and ambiguous evidence

## v0.2.1 — document and batch hardening
- [x] layout-preserved PDF table rows with explicit parameter/value headers
- [x] side-by-side numeric parameter/value reconstruction for common technical datasheets
- [x] explicit wrapped offered-value continuations and hyphenated parameter-label continuations
- [x] broader engineering unit normalization for electrical, pressure, length, mass, force and temperature units
- [x] sanitized motor, pump and valve datasheet fixtures with page provenance
- [x] Markdown multi-vendor tabulation export
- [x] compact `rank --top N` terminal display while preserving complete exports

## v0.2.2 — advanced layout reconstruction
- [x] coordinate-aligned sparse table rows where intermediate cells are visually blank
- [x] conservative handling for explicit merged-cell geometry
- [x] repeated explicit side-by-side header groups without positional guessing

## v0.3 — optional AI extraction
- [x] provider-neutral structured extraction interface
- [x] confidence and provenance validation
- [x] no AI dependency in deterministic evaluation

## v0.4 — MCP
- [x] MCP server exposing extract / compare / explain tools
- [x] support for long-running document jobs

## v0.5 — engineering ecosystem
- [x] IFC property inputs
- [x] supplier-scorecard technical-compliance export contract
- [x] technical bid tabulation workbook export

## v0.6 — structured vendor workbooks
- [x] dependency-free XLSX vendor input for explicit parameter/value tables
- [x] sheet and row provenance for workbook facts
- [x] repeated explicit header groups without positional guessing
- [x] reject formula-driven cells instead of trusting potentially stale cached results
- [ ] mixed PDF / XLSX / IFC CLI ergonomics and documentation hardening
- [ ] sanitized real-world vendor workbook fixtures
