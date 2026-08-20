# Roadmap

## v0.1 — deterministic core
- [x] PDF text extraction with page provenance
- [x] requirement extraction
- [x] vendor fact extraction
- [x] PASS / DEVIATION / MISSING / REVIEW
- [x] JSON / CSV / Markdown outputs
- [x] CI on Python 3.11–3.13

## v0.2.0 — real-world engineering workflow
- [x] deterministic unit conversion for core power, pressure, length and flow units
- [x] deterministic colon, two-column and paired-line vendor field extraction
- [x] conservative engineering terminology packs and project-specific JSON aliases
- [x] batch vendor ranking with HTML matrix and CSV audit exports
- [x] explicit uncertainty rules for missing, incompatible and ambiguous evidence

## v0.2.x — hardening and document coverage
- [x] layout-preserved PDF table rows with explicit parameter/value headers
- [x] side-by-side numeric parameter/value reconstruction for common technical datasheets
- [ ] merged/wrapped table cells and advanced multi-column layout reconstruction
- [x] broader engineering unit normalization for electrical, pressure, length, mass, force and temperature units
- [ ] additional sanitized real-world datasheet fixtures
- [ ] batch comparison ergonomics and export refinements

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
