# Roadmap

## v0.1 — deterministic core
- PDF text extraction with page provenance
- requirement extraction
- vendor fact extraction
- PASS / DEVIATION / MISSING / REVIEW
- JSON / CSV / Markdown outputs
- CI on Python 3.11–3.13

## v0.2 — real-world engineering documents
- [x] deterministic unit conversion for core power, pressure, length and flow units
- [x] deterministic colon, two-column and paired-line vendor field extraction
- [ ] complex PDF table and multi-column layout reconstruction
- [ ] broader engineering unit normalization
- [ ] explicit engineering synonym packs
- [ ] batch vendor comparison improvements

## v0.3 — optional AI extraction
- provider-neutral structured extraction interface
- confidence and provenance validation
- no AI dependency in deterministic evaluation

## v0.4 — MCP
- MCP server exposing extract / compare / explain tools
- support for long-running document jobs

## v0.5 — engineering ecosystem
- IFC property inputs
- supplier-scorecard technical-compliance export contract
- technical bid tabulation workbook export
