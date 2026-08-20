# Technical bid tabulation workbook export

`bidlint rank` can write a native `.xlsx` technical bid tabulation without changing the deterministic ranking or finding model.

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf \
  --output technical-tabulation.xlsx
```

The workbook is generated locally and contains no formulas, macros, external links or network dependencies. All values are precomputed from the same `ComplianceReport` objects used by JSON, CSV, Markdown and HTML exports.

## Workbook structure

### `Ranking`

Executive summary of the vendor order:

- deterministic rank
- vendor name
- compliance score
- `PASS` count
- `DEVIATION` count
- `MISSING` count
- `REVIEW` count

The ranking order is identical to terminal, JSON, HTML and Markdown portfolio outputs:

1. higher compliance score
2. fewer `DEVIATION + MISSING` findings
3. fewer `REVIEW` findings
4. vendor name

### `Matrix`

Requirement-by-vendor review matrix.

The first three columns are:

- requirement ID
- normalized parameter
- required value / comparator

Each vendor then receives one column. A vendor cell contains three lines:

```text
PASS
11 kW
Offered 11kw satisfies >= 10kw.
```

Status cells use distinct fills for `PASS`, `DEVIATION`, `MISSING` and `REVIEW`. The first three columns and top four rows are frozen to keep requirement context visible when reviewing large tabulations.

### `Audit`

Long-form evidence table designed for filtering and downstream audit work.

Columns include:

- rank
- vendor
- compliance score
- status
- requirement ID
- parameter
- required value
- offered value
- match confidence
- specification page / section
- vendor page / section
- deterministic reason

This sheet preserves the provenance available in the core models. PDF page numbers are written when present; IFC provenance remains available through the source-section field.

## Spreadsheet behavior

The workbook includes:

- fixed, readable column widths
- wrapped matrix and reason text
- frozen headers
- autofilters on all review tables
- status-specific cell fills
- literal percentage-point formatting for bidlint's 0–100 compliance score
- a formula-free package for predictable review

No hidden calculations are used. Opening the workbook in Excel or another compatible spreadsheet application does not recompute technical compliance.

## Deterministic package generation

The `.xlsx` file is written as an OOXML ZIP package using the Python standard library. ZIP entry timestamps are fixed, so the same report data and bidlint version produce byte-identical workbook output.

The export deliberately avoids introducing a spreadsheet runtime dependency into the base package.

## Limits

Excel format limits are enforced rather than silently truncating data:

- maximum 1,048,576 rows per sheet
- maximum 16,384 columns
- maximum 32,767 characters per cell

If a matrix would exceed the column limit, or an audit would exceed the row limit, bidlint raises an explicit error.

Cell text longer than Excel's cell-text limit is conservatively truncated with an ellipsis. The canonical machine-readable JSON report remains the preferred source when full unbounded reason text is required.

## Safety boundary

The workbook is a presentation/export layer only. It does not:

- change vendor ranking
- recalculate compliance
- convert `REVIEW` into a decision
- infer missing evidence
- add commercial or price scoring
- use formulas to derive hidden results

Technical acceptance remains an engineering decision outside bidlint.
