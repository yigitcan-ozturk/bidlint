# Architecture

```text
Specification PDF ──> page-preserving extraction ─────────────> requirement parser ──┐
                                                                                    │
                                                                                    ├─> deterministic matcher ─> compliance report
                                                                                    │
Vendor PDF ─────────> layout-preserving extraction ─> vendor fact parser ───────────┘
```

## Boundaries

### Extraction
Keeps source page numbers so every finding remains auditable. Vendor datasheets use pypdf layout-preserving text extraction so explicit horizontal table structure can be inspected without introducing OCR or AI inference.

### Requirement parsing
Identifies normative language (`shall`, `must`, `minimum`, `maximum`, etc.) and extracts simple numeric comparison rules.

### Vendor fact parsing
Reads explicit `parameter: value` facts, two-column rows, conservative paired-line fields, recognized table headers, and numeric side-by-side field pairs. Unrecognized multi-column layouts are skipped rather than flattened into guessed facts.

### Matching
Uses deterministic lexical similarity and a configurable threshold. Synonyms are explicit and reviewable.

### Evaluation
Numeric requirements are evaluated with explicit operators. Unsupported/qualitative comparisons become `REVIEW`, not guessed PASS/FAIL results.

## Planned AI layer

The future AI adapter may propose normalized parameters and structured requirements, but the adapter output will be validated into the same deterministic data model. The comparison engine remains provider-independent.
