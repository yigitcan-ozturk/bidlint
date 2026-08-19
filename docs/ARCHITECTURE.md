# Architecture

```text
Specification PDF ──> page-preserving extraction ──> requirement parser ──┐
                                                                          │
                                                                          ├─> deterministic matcher ─> compliance report
                                                                          │
Vendor PDF ─────────> page-preserving extraction ──> vendor fact parser ──┘
```

## Boundaries

### Extraction
Keeps source page numbers so every finding remains auditable.

### Requirement parsing
Identifies normative language (`shall`, `must`, `minimum`, `maximum`, etc.) and extracts simple numeric comparison rules.

### Vendor fact parsing
Reads explicit `parameter: value` facts. v0.1 intentionally favors transparent structured datasheets over opaque inference.

### Matching
Uses deterministic lexical similarity and a configurable threshold. Synonyms are explicit and reviewable.

### Evaluation
Numeric requirements are evaluated with explicit operators. Unsupported/qualitative comparisons become `REVIEW`, not guessed PASS/FAIL results.

## Planned AI layer

The future AI adapter may propose normalized parameters and structured requirements, but the adapter output will be validated into the same deterministic data model. The comparison engine remains provider-independent.
