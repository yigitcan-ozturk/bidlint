# Changelog

## Unreleased

### Added

- deterministic engineering unit conversion for power (`W`, `kW`, `MW`)
- deterministic engineering unit conversion for pressure (`Pa`, `kPa`, `MPa`, `bar`)
- deterministic engineering unit conversion for length (`mm`, `cm`, `m`)
- deterministic engineering unit conversion for flow (`L/s`, `m³/s`, `m³/h`)
- explicit dimension-safety: incompatible or unknown unit pairs remain `REVIEW`
- conversion-aware finding explanations such as `10000w (= 10kw)`

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
