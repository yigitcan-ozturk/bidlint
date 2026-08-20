# bidlint

**Lint technical bids against specifications. Evidence before confidence.**

![bidlint technical bid compliance workflow](docs/assets/bidlint-overview.svg)

[![Tests](https://github.com/yigitcan-ozturk/bidlint/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/bidlint/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/yigitcan-ozturk/bidlint)](https://github.com/yigitcan-ozturk/bidlint/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`bidlint` is an open-source technical bid compliance engine for comparing engineering specifications with vendor datasheets, bids and submittals.

It turns document evidence into explicit `PASS / DEVIATION / MISSING / REVIEW` findings, keeps source-page provenance, performs deterministic engineering comparisons where possible, and refuses to fabricate certainty where it cannot.

> Latest stable release: **v0.2.1**

```text
Specification PDF ──> requirements ──┐
                                     ├──> terminology + unit-aware rules ──> findings
Vendor submittal ────> offered facts ┘                              │
                                                                    ├──> JSON / CSV / Markdown / HTML
Multiple vendors ────────────────────────────────────────────────────└──> technical bid tabulation
```

## The problem

Technical bid evaluation is still often performed by reading specifications and vendor submittals side-by-side, copying values into spreadsheets, and manually tracking deviations.

`bidlint` focuses on one narrow question:

> **What did the specification require, what did the vendor offer, and where is the evidence?**

The deterministic core does not need an LLM or an external API.

## 30-second demo

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
REVIEW     R0004  housing — qualitative comparison requires review.
MISSING    R0005  flow rate — no sufficiently similar vendor parameter found.
```

For a reproducible walkthrough, see the [`five-minute demo`](docs/QUICKSTART.md).

## Multi-vendor technical bid tabulation

Compare several vendors against the same specification:

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

Generate a self-contained HTML comparison with a ranking summary and requirement-by-vendor matrix:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf \
  --output technical-tabulation.html
```

Export the same review matrix as Markdown:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf \
  --output technical-tabulation.md
```

Or export a long-form audit CSV that can be filtered, pivoted or imported into procurement workflows:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf \
  --output technical-tabulation.csv
```

For large vendor sets, `--top N` limits terminal display without truncating exported data.

See [`docs/BATCH_COMPARISON.md`](docs/BATCH_COMPARISON.md).

## Engineering-safe comparison

### Unit conversion

Known units in the same physical dimension are converted deterministically.

```text
Specification: Motor power shall be minimum 10 kW.
Vendor       : Motor power: 10000 W

PASS — Offered 10000w (= 10kw) satisfies >= 10kw.
```

Deterministic families include real power, voltage, current, frequency, apparent power, pressure, length, mass, force, flow and explicit temperature units. Missing, unknown or dimensionally incompatible units remain `REVIEW`.

See [`docs/ENGINEERING_UNITS.md`](docs/ENGINEERING_UNITS.md).

### Vendor datasheet layouts

Vendor facts can be extracted from several explicit layouts:

```text
Motor power: 11 kW
```

```text
Motor power        11 kW
Design pressure    10 bar
```

```text
Motor power
11000 W
```

```text
Housing material:
316L stainless steel
```

Layout-preserved tables with explicit headers, side-by-side numeric fields, final offered values wrapped to the next numeric line, and explicitly hyphenated parameter continuations are also supported conservatively.

Descriptive material grades such as `316L stainless steel` stay qualitative; they are not silently converted into a numeric value of `316`.

See [`docs/VENDOR_PARSING.md`](docs/VENDOR_PARSING.md).

### Engineering terminology

Built-in terminology aliases normalize a deliberately small set of low-risk nomenclature variants:

```text
ingress protection rating -> ip rating
flow-rate                 -> flow rate
rotation speed            -> rotational speed
rated motor power         -> motor power
```

Project- or vendor-specific terminology can be declared explicitly:

```json
{
  "rated output": "motor power",
  "supplier ip code": "ip rating"
}
```

```bash
bidlint compare specification.pdf vendor.pdf --aliases aliases.json
```

Ambiguous concepts are intentionally not collapsed automatically. For example, `protection class` is not assumed to mean `ip rating`.

See [`docs/TERMINOLOGY.md`](docs/TERMINOLOGY.md).

## Status model

| Status | Meaning |
| --- | --- |
| `PASS` | Offered value deterministically satisfies the requirement |
| `DEVIATION` | Offered value deterministically violates the requirement |
| `MISSING` | No sufficiently similar vendor parameter was found |
| `REVIEW` | Evidence exists, but the comparison is qualitative, ambiguous or not safely deterministic |

`REVIEW` is a feature, not a fallback. The engine prefers explicit uncertainty over a false compliance decision.

## Outputs

### Single vendor

```bash
bidlint compare specification.pdf vendor.pdf --output compliance.json
bidlint compare specification.pdf vendor.pdf --output compliance.csv
bidlint compare specification.pdf vendor.pdf --output compliance.md
bidlint compare specification.pdf vendor.pdf --output compliance.html
```

### Multiple vendors

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output ranking.json
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output ranking.csv
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output ranking.md
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output ranking.html
```

JSON is the machine-readable integration contract. CSV is optimized for tabular workflows. Markdown is convenient for code/design review. HTML is self-contained and designed for human review.

## Quick start

Requirements:

- Python 3.11+
- text-based PDFs

Install from source:

```bash
git clone https://github.com/yigitcan-ozturk/bidlint.git
cd bidlint
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Inspect extraction before comparing:

```bash
bidlint extract specification.pdf --kind specification
bidlint extract vendor.pdf --kind vendor
```

## Design principles

**Evidence before confidence.** Every result should remain traceable to its source document.

**Deterministic where possible.** Numeric limits, unit conversions and explicit terminology mappings belong in code, not model opinion.

**Explicit uncertainty.** Unsupported or ambiguous comparisons remain `REVIEW`.

**Provider-independent core.** Future AI-assisted extraction is an adapter to the deterministic model, not the authority that decides compliance.

**Engineering first.** The project is designed around specification/submittal workflows rather than generic document chat.

## Architecture

```text
PDF extraction
    │
    ├── specification ──> requirement parser ─────────────┐
    │                                                     │
    └── vendor ────────> structured fact parser ──────┐   │
                                                       ▼   ▼
                                               terminology matcher
                                                       │
                                                       ▼
                                               unit-aware evaluator
                                                       │
                                ┌──────────────────────┼───────────────────┐
                                ▼                      ▼                   ▼
                           single report          vendor ranking      audit exports
```

Detailed references:

- [`Architecture`](docs/ARCHITECTURE.md)
- [`Decision model`](docs/DECISION_MODEL.md)
- [`Data contract`](docs/DATA_CONTRACT.md)
- [`Engineering units`](docs/ENGINEERING_UNITS.md)
- [`Vendor parsing`](docs/VENDOR_PARSING.md)
- [`Terminology`](docs/TERMINOLOGY.md)
- [`Batch comparison`](docs/BATCH_COMPARISON.md)

## Current limits

The limits are explicit by design:

- scanned/image-only PDFs require OCR before processing
- arbitrary merged-cell reconstruction is not implemented
- sparse or ambiguous multi-column layouts may still need preprocessing
- only documented engineering unit families are converted automatically
- qualitative requirements remain `REVIEW` without an explicit deterministic rule
- terminology aliases are conservative unless the user provides a project-specific mapping

## Roadmap

See [`ROADMAP.md`](ROADMAP.md). v0.2.1 hardens realistic vendor PDF layouts, engineering units, sanitized fixtures and batch review exports. v0.2.2 is reserved for coordinate-aware sparse/merged-cell reconstruction before the optional AI extraction milestone.

Later milestones include optional AI-assisted structured extraction, MCP, IFC property inputs and a direct technical-compliance contract for `supplier-scorecard`.

## Procurement / engineering tooling

`bidlint` is designed as the technical-compliance signal in a broader explainable procurement toolchain:

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

GitHub Actions targets Python 3.11, 3.12 and 3.13 and can also be started manually through `workflow_dispatch`.

## Security and confidential documents

Technical documents may contain confidential project, vendor or commercial information. The deterministic core runs locally and does not transmit documents to an external AI API.

See [`SECURITY.md`](SECURITY.md) before exposing document processing as a network service.

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md). High-value early contributions include sanitized real-world requirement patterns, unit cases, terminology edge cases and false-positive parsing examples.

## License

MIT. See [`LICENSE`](LICENSE).
