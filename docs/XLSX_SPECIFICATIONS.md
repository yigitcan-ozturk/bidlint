# XLSX specifications

BidLint accepts a conservative XLSX specification shape for technical pilot workflows where the source tender is a structured workbook rather than normative PDF prose.

## Required shape

Select one visible worksheet. Within the first 20 populated rows it must contain exactly one requirement-name column and one requirement-value column. Supported header names include:

- `General Requirement` / `Specification`
- `Requirement` / `Required Value`
- `Parameter` / `Value`

Only the contiguous populated requirement block immediately below that header is consumed. A blank-row boundary ends the block. Later item schedules are intentionally ignored until BidLint has an explicit item-scoping model.

Example:

| General Requirement | Specification |
| --- | --- |
| Material | Grade 304 stainless steel, BS EN 10088 |
| Load Class | A15 |
| Grating | Plain ladder grating |
| Outlet | DN110 / KV110 vertical outlet |
| Drawings | Supplier to develop fabrication and approval drawings |
| Equivalents | Technically compliant equivalent products are acceptable |

Qualitative designations such as `Grade 304` and `A15` remain qualitative and therefore route to `REVIEW` after a vendor match. Explicit scalar rules such as `minimum 1.5 mm` retain normal deterministic numeric comparison semantics.

## Worksheet selection

For the CLI:

```bash
bidlint compare specification.xlsx vendor.pdf --spec-xlsx-sheet "Technical Requirements"
```

For a pilot manifest:

```json
{
  "options": {
    "spec_xlsx_sheet": "Technical Requirements"
  }
}
```

`spec_xlsx_sheet` selects the specification workbook only. Vendor XLSX selection remains independently controlled by `xlsx_sheet`.

## Safety and ambiguity rules

Specification XLSX parsing keeps the existing workbook archive protections for macros and external relationships. Formula cells remain rejected. Presentation-only merged cells may exist; BidLint reads only the actual stored cell text and never expands or infers merged values.

Commercial columns are not technical evidence merely because they appear in the same workbook. They must be removed from a sanitized external-pilot copy before the sanitization gate can pass.

An XLSX pilot is not approved simply because it executes. The normal sanitization scan, non-empty evaluated-requirement gate, deterministic replay, human technical review and release gate remain mandatory.
