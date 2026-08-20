# Changelog

## Unreleased

### Added

- layout-preserving PDF extraction for vendor datasheets using pypdf layout mode
- deterministic header-driven parsing for tables with explicit parameter, unit and offered-value columns
- conservative parsing for two numeric parameter/value pairs rendered side-by-side on one visual row
- regression coverage for table footers, unrelated multi-column metadata and end-to-end compliance evaluation

### Changed

- ambiguous unrecognized 3+ column vendor rows are skipped instead of being flattened into false two-column facts
- development version advanced to `0.2.1.dev0`

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
