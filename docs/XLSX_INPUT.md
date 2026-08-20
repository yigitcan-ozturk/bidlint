# XLSX vendor input

`bidlint` v0.6 development can read vendor facts directly from `.xlsx` workbooks without adding a spreadsheet runtime dependency.

The reader is deliberately conservative. It recognizes only explicit table structures where the workbook itself labels the semantic columns.

## Supported table shape

A supported table contains a header row with:

- a parameter-like header: `Parameter`, `Property`, `Description`, `Technical Parameter` or `Item`
- an offered-value header: `Offered`, `Offered Value`, `Vendor Value`, `Supplier Value` or `Value`
- an optional `Unit` / `Units` column between the parameter and offered-value columns

Example:

| Parameter | Unit | Offered |
| --- | --- | --- |
| Motor power | kW | 11 |
| Design pressure | bar | 10 |
| Housing |  | 316L stainless steel |

The first two rows become numeric vendor facts with normalized units. `316L stainless steel` stays qualitative and is not silently converted into a numeric value.

Repeated explicit header groups on the same row are also supported. Each offered-value column is paired only with the nearest preceding explicit parameter-like header in its group; arbitrary positional guessing is not used.

## Provenance

Workbook evidence uses the existing `SourceRef` model:

- `document`: workbook file name
- `section`: worksheet name
- `line`: worksheet row number
- `page`: unset because XLSX sheets are not page-addressed documents

This makes workbook evidence auditable in the same comparison and export pipeline used for PDF and IFC inputs.

## CLI

Use an XLSX vendor input anywhere a normal vendor input is accepted:

```bash
bidlint extract vendor-offer.xlsx --kind vendor
```

```bash
bidlint compare specification.pdf vendor-offer.xlsx
```

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.xlsx
```

## Deterministic safety rules

The XLSX reader intentionally does not behave like a spreadsheet calculation engine.

- Formula cells are rejected instead of trusting cached values that may be stale.
- Missing intermediate cells are not inferred by position.
- A blank row terminates the current recognized table.
- `Note`, `Notes`, `Remark`, `Remarks` and `General Notes` terminate a recognized table when they appear in its parameter column.
- Workbook and XML member sizes are bounded before parsing.
- External workbook relationships are not followed.
- Unsupported or ambiguous workbook layouts produce no invented vendor facts.

## Scope

This milestone is for structured vendor evidence, not arbitrary Excel understanding. Charts, macros, pivot tables, merged semantic headers, calculated formulas and layout-only spreadsheets remain outside the deterministic input contract until they can be supported without weakening evidence quality.
