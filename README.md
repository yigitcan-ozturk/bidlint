# bidlint

**Lint technical bids against specifications. Evidence before confidence.**

[![Tests](https://github.com/yigitcan-ozturk/bidlint/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/bidlint/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`bidlint` is an open-source engineering compliance engine for comparing text-based technical specification PDFs with vendor datasheets, bids and submittals.

It extracts normative requirements, matches them to offered parameters, evaluates deterministic numeric rules, and produces an auditable compliance matrix with source-page traceability.

```text
Specification PDF ──> requirements ──┐
                                     ├──> deterministic comparison ──> PASS / DEVIATION / MISSING / REVIEW
Vendor submittal ────> offered facts ┘
```

## Why

Technical bid evaluation is still frequently performed by manually reading specifications, datasheets, quotations and submittals side-by-side. The work is repetitive, difficult to audit and easy to lose in spreadsheets.

`bidlint` focuses on one narrow problem:

> **What did the specification require, what did the vendor offer, and where is the evidence?**

The project deliberately separates deterministic engineering rules from future AI-assisted extraction. A model may eventually help normalize messy language, but it should not silently decide whether `54 >= 65`.

## Demo

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf
```

```text
BIDLINT — TECHNICAL COMPLIANCE
================================
Score      : 50.0%
PASS       : 2
DEVIATION  : 1
MISSING    : 1
REVIEW     : 1

PASS       R0001  motor efficiency — Offered 93% satisfies >= 90%.
PASS       R0002  noise level — Offered 68db satisfies <= 70db.
DEVIATION  R0003  ip rating — Offered 54 does not satisfy >= 65.
REVIEW     R0004  housing — Matched a vendor parameter, but the requirement is qualitative...
MISSING    R0005  flow rate — No sufficiently similar vendor parameter was found.
```

Machine-readable result:

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf --json
```

Export a technical compliance matrix:

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf --output compliance.csv
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf --output compliance.md
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf --output compliance.json
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf --output compliance.html
```

Rank multiple vendors against the same specification:

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf
```

```text
BIDLINT — VENDOR RANKING
================================
 1. vendor-b-submittal.pdf         100.0%  PASS 4  DEV 0  MISS 0  REVIEW 1
 2. vendor-a-submittal.pdf          50.0%  PASS 2  DEV 1  MISS 1  REVIEW 1
```

## What v0.1 can do

- extract page-preserving text from technical PDFs
- identify normative language such as `shall`, `must`, `minimum`, `maximum`, `at least` and `not exceed`
- parse simple numeric engineering requirements into explicit operators
- extract vendor `parameter: value` facts
- match requirement parameters to offered parameters with transparent similarity rules
- classify findings as `PASS`, `DEVIATION`, `MISSING` or `REVIEW`
- retain source page references for auditability
- export JSON, CSV, Markdown and self-contained HTML reports
- rank multiple vendor submittals against one specification
- run without an LLM or external API

## Status semantics

| Status | Meaning |
| --- | --- |
| `PASS` | Offered numeric value deterministically satisfies the requirement |
| `DEVIATION` | Offered numeric value deterministically violates the requirement |
| `MISSING` | No sufficiently similar offered parameter was found |
| `REVIEW` | A match exists, but the comparison is qualitative, ambiguous or unit-sensitive |

`REVIEW` is intentional. The engine prefers an explicit human-review state over fabricating certainty.

## Quick start

### Requirements

- Python 3.11+
- text-based PDFs (OCR is not included in v0.1)

### Install from source

```bash
git clone https://github.com/yigitcan-ozturk/bidlint.git
cd bidlint
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Compare two documents

```bash
bidlint compare specification.pdf vendor-submittal.pdf
```

### Rank multiple vendors

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf vendor-c.pdf
```

### Inspect extraction

```bash
bidlint extract specification.pdf --kind specification
bidlint extract vendor-submittal.pdf --kind vendor
```

## Example JSON contract

```json
{
  "tool": "bidlint",
  "version": "0.1.0",
  "specification": "pump-specification.pdf",
  "vendor": "vendor-a-submittal.pdf",
  "compliance_score": 50.0,
  "counts": {
    "PASS": 2,
    "DEVIATION": 1,
    "MISSING": 1,
    "REVIEW": 1
  },
  "findings": []
}
```

The full finding objects include the original requirement, matched vendor fact, confidence, decision reason and document/page provenance.

## Design principles

### 1. Evidence before confidence
Every result should point back to the document that produced it.

### 2. Deterministic where possible
Numeric limits, thresholds and policy rules should be evaluated by code, not language-model opinion.

### 3. Explicit uncertainty
If the engine cannot safely compare a requirement, it returns `REVIEW`.

### 4. Provider-independent core
The deterministic model does not depend on an AI vendor. Future AI extraction is an adapter, not the decision engine.

### 5. Engineering first
The project is designed around real specification/submittal workflows rather than generic document chat.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DECISION_MODEL.md`](docs/DECISION_MODEL.md) and [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).

```text
PDF
 │
 ▼
page-preserving extraction
 │
 ├──────── specification ────────> requirement parser
 │                                      │
 └──────── vendor submittal ─────> vendor fact parser
                                        │
                  ┌─────────────────────┘
                  ▼
            parameter matcher
                  │
                  ▼
          deterministic evaluator
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
      JSON       CSV    Markdown / HTML
```

## Current limits

v0.1 intentionally starts with a narrow, auditable core.

- scanned/image-only PDFs require OCR before processing
- complex tables and multi-column layouts may need pre-processing
- unit conversion is not yet automatic
- qualitative requirements are routed to `REVIEW`
- vendor parsing currently favors explicit `parameter: value` datasheet lines

These constraints are visible by design rather than hidden behind an AI confidence score.

## Roadmap

The next milestones are documented in [`ROADMAP.md`](ROADMAP.md):

- stronger engineering unit normalization
- stronger table and multi-line datasheet extraction
- optional AI-assisted structured extraction
- MCP server
- IFC property inputs
- direct technical-compliance contract for `supplier-scorecard`

## Procurement / engineering tooling

`bidlint` is designed to become the technical-compliance input to the existing procurement decision suite:

```text
currency-normalizer ──> rfqdiff ────────────────┐
                                                 │
payment-terms-parser ───────────────────────────┼──> supplier-scorecard
                                                 │
vendor-risk-engine ─────────────────────────────┤
                                                 │
bidlint ──> technical compliance ───────────────┘
```

## Development

```bash
pip install -e '.[dev]'
pytest -q
ruff check src tests
```

GitHub Actions tests Python 3.11, 3.12 and 3.13.

## Security and confidential documents

Technical documents may contain confidential project, vendor or commercial information. `bidlint` v0.1 performs local deterministic processing and does not transmit documents to an external AI API.

See [`SECURITY.md`](SECURITY.md) before exposing document processing as a network service.

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md). The most valuable early contributions are sanitized real-world requirement patterns, unit cases and false-positive matching examples.

## License

MIT. See [`LICENSE`](LICENSE).
