# bidlint

**Lint technical bids against specifications. Evidence before confidence.**

![bidlint technical bid compliance workflow](docs/assets/bidlint-overview.svg)

[![Tests](https://github.com/yigitcan-ozturk/bidlint/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/bidlint/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/yigitcan-ozturk/bidlint)](https://github.com/yigitcan-ozturk/bidlint/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`bidlint` is an open-source, deterministic technical-bid compliance engine. It compares engineering specifications with vendor datasheets, submittals, multi-document packages, explicit XLSX offer tables and explicitly scoped IFC properties while preserving source evidence.

> Latest stable release: **v1.1.0**
>
> v1.1.0 adds production-adoption controls: guarded sanitization scanning, manifest-driven repeatability evidence, explicit XLSX specification scope coverage, deliberate human release-gate approval and immutable baseline replay verification. The frozen BidLint 1.x compliance semantics are unchanged.

## Why BidLint

Technical bid evaluation is often performed by reading specifications and vendor submissions side-by-side, copying values into spreadsheets and manually tracking deviations. BidLint narrows the problem to three auditable questions:

> **What did the specification require? What did the vendor offer? Where is the evidence?**

The deterministic core does not require an LLM or external API. It prefers explicit uncertainty over fabricated certainty.

## Status model

| Status | Meaning |
| --- | --- |
| `PASS` | Offered evidence deterministically satisfies the requirement |
| `DEVIATION` | Offered evidence deterministically violates the requirement |
| `MISSING` | No sufficiently similar vendor evidence was found |
| `REVIEW` | Evidence exists, but the comparison is qualitative, ambiguous or unsafe to decide automatically |

These meanings, together with the 1.x scoring and public CLI/error contract, are frozen by [`docs/STABLE_CONTRACT.md`](docs/STABLE_CONTRACT.md).

## Quick start

Requirements: Python 3.11+ and text-based PDFs for PDF extraction. IFC support is optional.

```bash
git clone https://github.com/yigitcan-ozturk/bidlint.git
cd bidlint
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Compare one vendor:

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf
```

Rank several vendors:

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf \
  --output technical-tabulation.xlsx
```

Inspect evidence before comparing:

```bash
bidlint extract specification.pdf --kind specification
bidlint extract vendor.pdf --kind vendor
bidlint extract vendor.xlsx --kind vendor --xlsx-sheet "Technical Offer"
```

## Supported evidence

BidLint routes supported inputs into the same `Requirement` / `VendorFact` / deterministic evaluator boundary:

```text
Specification PDF / XLSX ──> requirements ──────────────┐
                                                         │
Vendor PDF ────────────────> facts ──────────────────────┤
Vendor XLSX ───────────────> facts ──────────────────────┤
IFC element ───────────────> facts ──────────────────────┤
Vendor package ────────────> classify + consolidate ─────┤
optional structured source -> evidence validation ───────┤
                                                         ▼
                                               terminology matcher
                                                         │
                                                         ▼
                                               unit-aware evaluator
                                                         │
                           ┌─────────────────────────────┼──────────────────────────┐
                           ▼                             ▼                          ▼
                     single report                vendor ranking             audit / ecosystem
```

Key behaviors are conservative by design:

- compatible engineering units are converted deterministically;
- unknown, missing or dimensionally incompatible units remain `REVIEW`;
- descriptive grades such as `316L stainless steel` remain qualitative;
- formulas, macros, external XLSX relationships and ambiguous spreadsheet evidence are rejected rather than evaluated;
- IFC inputs require explicit element scope;
- package evidence priority is explicit and opt-in; conflicting evidence remains reviewable with provenance.

Reference documentation: [`ENGINEERING_UNITS`](docs/ENGINEERING_UNITS.md), [`VENDOR_PARSING`](docs/VENDOR_PARSING.md), [`VENDOR_PACKAGES`](docs/VENDOR_PACKAGES.md), [`XLSX_VENDOR_INPUT`](docs/XLSX_VENDOR_INPUT.md), [`IFC`](docs/IFC.md), [`TERMINOLOGY`](docs/TERMINOLOGY.md) and [`BATCH_COMPARISON`](docs/BATCH_COMPARISON.md).

## Outputs and procurement hand-off

Single-vendor and multi-vendor workflows support machine-readable and review-oriented outputs including JSON, CSV, Markdown, HTML and formula-free XLSX tabulation.

The procurement workflow adds explicit technical knockouts, clarification and unanswered registers, deviation/review queues, procurement-ready ranking and a versioned supplier-scorecard technical-compliance hand-off. BidLint does **not** add commercial scoring, contractual acceptance or inferred knockout criteria.

See [`docs/KNOCKOUTS.md`](docs/KNOCKOUTS.md), [`docs/SUPPLIER_SCORECARD.md`](docs/SUPPLIER_SCORECARD.md) and [`docs/WORKBOOK_EXPORT.md`](docs/WORKBOOK_EXPORT.md).

## Production adoption in v1.1

The v1.1 toolchain turns a real sanitized pilot into reproducible release evidence:

```bash
bidlint-pilot-init ./pilot --pilot-id external-pilot-001 --vendors 1
bidlint-pilot-scan ./pilot/pilot.json --json --output ./pilot/evidence/sanitization-scan.json
bidlint-pilot ./pilot/pilot.json --json --output ./pilot/evidence/pilot-evidence.json
bidlint-pilot-verify approved-baseline.json current-evidence.json --json
bidlint-pilot-gate ./pilot --json
```

The gate requires a blocker-free sanitization scan, explicit human sanitization and technical approval, review of all non-PASS outcomes, explicit specification-scope review when required, regression coverage for known product defects and an exact approved-baseline replay.

The final v1.1 release gate used a real external drainage-schedule-derived private sanitized corpus. Six top-level requirements were evaluated conservatively, and 37 later populated XLSX rows were surfaced as a manual-scope boundary instead of being silently counted as covered. Raw external/customer documents were not committed. Non-sensitive evidence is recorded in Issue #39.

See [`docs/PRODUCTION_ADOPTION.md`](docs/PRODUCTION_ADOPTION.md), [`docs/PILOT_SANITIZATION.md`](docs/PILOT_SANITIZATION.md), [`docs/PILOT_RELEASE_GATE.md`](docs/PILOT_RELEASE_GATE.md) and [`docs/PILOT_BASELINES.md`](docs/PILOT_BASELINES.md).

## Optional integrations

BidLint also includes additive boundaries around the deterministic core:

- provider-neutral structured extraction with page-local evidence validation;
- optional local MCP server and bounded persisted document jobs;
- supplier-scorecard technical-compliance export;
- explicitly scoped IFC property evidence.

Optional providers and MCP clients cannot decide `PASS`, `DEVIATION`, `MISSING` or `REVIEW`; the deterministic evaluator remains authoritative.

## Quality gates

Release candidates are validated with:

- ruff + pytest on Python 3.11, 3.12 and 3.13;
- wheel/sdist build, twine check, installed CLI smoke and `pip check`;
- runtime dependency audit;
- deterministic 20,000-fact consolidation benchmark;
- production-shaped conflict-path CPU and peak-memory profiling.

See [`.github/workflows`](.github/workflows) and [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md).

## Explicit limits

BidLint intentionally does not pretend to solve unsupported document semantics. Current boundaries include image-only PDFs without OCR, arbitrary unsupported table geometry, qualitative requirements without deterministic rules, nested vendor-package traversal, IFC geometry evaluation, hidden commercial decision logic and automatic contractual acceptance.

For XLSX specifications, only the explicit contiguous requirement block is evaluated automatically; later populated rows are surfaced as scope evidence for manual review rather than flattened into false requirements.

## Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest -q
```

See [`ROADMAP.md`](ROADMAP.md), [`CHANGELOG.md`](CHANGELOG.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md).

## License

MIT. See [`LICENSE`](LICENSE).
