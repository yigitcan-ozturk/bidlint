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

## v0.2.1 — document and batch hardening
- [x] layout-preserved PDF table rows with explicit parameter/value headers
- [x] side-by-side numeric parameter/value reconstruction for common technical datasheets
- [x] explicit wrapped offered-value continuations and hyphenated parameter-label continuations
- [x] broader engineering unit normalization for electrical, pressure, length, mass, force and temperature units
- [x] sanitized motor, pump and valve datasheet fixtures with page provenance
- [x] Markdown multi-vendor tabulation export
- [x] compact `rank --top N` terminal display while preserving complete exports

## v0.2.2 — advanced layout reconstruction
- [x] coordinate-aligned sparse table rows where intermediate cells are visually blank
- [x] conservative handling for explicit merged-cell geometry
- [x] repeated explicit side-by-side header groups without positional guessing

## v0.3 — optional AI extraction
- [x] provider-neutral structured extraction interface
- [x] confidence and provenance validation
- [x] no AI dependency in deterministic evaluation

## v0.4 — MCP
- [x] MCP server exposing extract / compare / explain tools
- [x] support for long-running document jobs

## v0.5 — engineering ecosystem
- [x] IFC property inputs
- [x] supplier-scorecard technical-compliance export contract
- [x] technical bid tabulation workbook export

## v0.6 — XLSX vendor inputs
- [x] explicit formula-free `.xlsx` vendor tables as `VendorFact` inputs
- [x] visible worksheet selection with `--xlsx-sheet`
- [x] row/sheet provenance preserved in normal compliance findings
- [x] conservative rejection of formulas, macros, external links, merged cells and ambiguous worksheet/header layouts
- [x] standard-library OOXML parsing with no spreadsheet runtime dependency
- [x] merge feature branch with full Python 3.11–3.13 CI green
- [x] freeze and publish stable v0.6.0 release

## v0.7 — real-world bid intake
- [x] deterministic direct-child multi-file vendor packages for PDF / XLSX / explicitly scoped IFC evidence
- [x] consolidate equivalent duplicate evidence across compatible engineering units
- [x] turn conflicting package evidence into explicit provenance-preserving `REVIEW` facts instead of choosing a winner
- [x] directory dispatch through the existing vendor-input boundary without changing the deterministic evaluator
- [ ] thread project-specific terminology aliases into CLI package consolidation
- [ ] explicit document classification for specification, datasheet, compliance schedule, technical offer and ignored documents
- [ ] explicit evidence-priority policy with user override rather than hidden source precedence
- [ ] fully scoped mixed-package ranking when IFC/XLSX selectors are required
- [ ] package-level audit surface for all contributing and conflicting evidence
- [ ] sanitized pump, motor, valve, HVAC and electrical multi-document package fixtures
- [ ] freeze and publish stable v0.7.0 release

## v0.8 — procurement workflow
- [ ] mandatory technical knockout criteria
- [ ] bidder clarification list and unanswered requirement register
- [ ] deviation register and review queue
- [ ] procurement-ready package ranking and supplier-scorecard hand-off

## v0.9 — production hardening
- [ ] malformed and adversarial PDF / XLSX / IFC regression suite
- [ ] deterministic large-package performance benchmarks
- [ ] structured CLI exit codes and error contracts
- [ ] package build, compatibility and security hardening

## v1.0 — stable contract
- [ ] freeze CLI, JSON, finding and VendorFact compatibility contracts
- [ ] freeze deterministic status and scoring semantics
- [ ] publish backward-compatibility and versioning policy
- [ ] release bidlint 1.0.0
