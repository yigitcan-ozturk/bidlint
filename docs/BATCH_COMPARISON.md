# Multi-vendor technical bid tabulation

`bidlint rank` compares multiple vendor submittals against the same specification and keeps the ranking deterministic and auditable.

## Terminal ranking

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf vendor-c.pdf
```

For large vendor sets, terminal output can be limited without changing any export:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf vendor-c.pdf \
  --top 2 \
  --output technical-tabulation.csv
```

`--top N` affects terminal display only. JSON, Markdown, HTML and CSV exports always retain the complete vendor set.

Ranking order is deterministic:

1. higher technical compliance score
2. fewer `DEVIATION + MISSING` findings
3. fewer `REVIEW` findings
4. vendor filename for a stable final tie-break

The ranking is a technical comparison only. It does not imply commercial award, purchasing approval or engineering acceptance.

## Markdown review export

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output technical-tabulation.md
```

Markdown includes the deterministic vendor ranking plus a requirement-by-vendor matrix with status, offered value and decision reason. It is useful for pull requests, issue discussions, design notes and review documents where a browser-only report is inconvenient.

## HTML technical bid tabulation

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output technical-tabulation.html
```

The self-contained HTML report includes:

- vendor ranking summary
- compliance scores and status counts
- requirement-by-vendor comparison matrix
- offered value in each cell
- deterministic reason for each status

It can be opened locally in a browser without an external service or AI API.

## CSV audit export

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output technical-tabulation.csv
```

CSV uses a long-form audit structure: one row per vendor per requirement.

Columns include:

- rank
- vendor
- compliance score
- status
- requirement ID and parameter
- required value
- offered value
- match confidence
- specification/vendor source page
- decision reason

This format is intentionally easy to filter, pivot or import into spreadsheet and procurement workflows.

## JSON portfolio

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --output technical-tabulation.json
```

JSON remains the machine-readable integration contract and includes both the ranking summary and full per-vendor reports.

## Terminology aliases

Batch comparison uses the same terminology model as single-vendor comparison:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf \
  --aliases aliases.json \
  --output technical-tabulation.html
```

## Deliberate limits

- ranking is based only on technical compliance findings
- commercial price, delivery, payment terms and vendor risk are outside `bidlint`
- unresolved `REVIEW` findings remain visible instead of being auto-approved
- spreadsheet workbook generation is a future integration layer; v0.2 exports interoperable CSV instead

The goal is not to replace engineering judgment. It is to make the technical comparison **structured, repeatable and evidence-preserving**.
