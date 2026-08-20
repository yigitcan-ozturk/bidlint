# XLSX vendor inputs

`bidlint v0.6` can consume an explicitly tabulated `.xlsx` vendor offer as technical evidence without adding a spreadsheet runtime dependency.

The workbook is treated as evidence, not as executable logic. `bidlint` reads cell values directly from OOXML and does not calculate formulas.

## Required table shape

The selected visible worksheet must contain an explicit header row within the first 20 populated rows.

At minimum it needs exactly one parameter-like column and exactly one offered-value column:

| Parameter | Unit | Offered | Section |
| --- | --- | --- | --- |
| Motor Power | kW | 11 | Electrical |
| Noise Level | dB | 68 | Acoustics |
| Housing Material |  | 316L stainless steel | Materials |

Accepted parameter headers are `Parameter`, `Property`, `Description`, `Technical Parameter`, or `Item`.

Accepted offered headers are `Offered`, `Offered Value`, `Vendor Value`, `Supplier Value`, or `Value`.

`Unit`/`Units` and `Section`/`Category`/`System` are optional.

## CLI

Single-vendor comparison:

```bash
bidlint compare specification.pdf supplier-offer.xlsx
```

Inspect extracted facts:

```bash
bidlint extract supplier-offer.xlsx --kind vendor
```

When a workbook has more than one visible worksheet, select one explicitly:

```bash
bidlint compare specification.pdf supplier-offer.xlsx --xlsx-sheet "Technical Offer"
```

XLSX inputs can participate in mixed multi-vendor ranking alongside PDF and explicitly scoped IFC inputs:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.xlsx vendor-c.ifc \
  --xlsx-sheet "Technical Offer" \
  --ifc-guid 1AbCdEfGhIjKlMnOpQrStu
```

The same `--xlsx-sheet` name is applied to `.xlsx` inputs in one `rank` command. If suppliers use different sheet names, run them separately or normalize the workbook sheet names before ranking.

## Provenance

A spreadsheet row becomes a normal `VendorFact`.

- `SourceRef.document` is the workbook filename.
- `SourceRef.line` is the worksheet row number.
- `SourceRef.section` is `XLSX:<worksheet>` plus the optional row section, for example `XLSX:Technical Offer/Electrical`.

The existing deterministic matcher, engineering-unit conversion and compliance evaluator remain authoritative after extraction.

## Safety boundary

The parser intentionally rejects workbook structures that would require execution or positional guessing:

- formulas
- VBA/macros
- external links
- hidden evidence worksheets
- merged cells in the selected worksheet
- multiple visible worksheets without `--xlsx-sheet`
- duplicate parameter/offered headers
- rows containing only a parameter or only an offered value
- conflicting units between the offered cell and explicit unit column

Boolean cells are preserved as qualitative `TRUE` / `FALSE` evidence rather than converted into numeric `1` / `0` compliance values.

The parser does not infer formulas, recalculate workbooks, follow links, unhide sheets, or reconstruct merged spreadsheet layouts.
