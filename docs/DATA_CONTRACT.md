# Data contract

The JSON result is designed to be consumed by scripts, CI pipelines and downstream procurement tools.

## Top-level fields

```json
{
  "tool": "bidlint",
  "version": "0.1.0",
  "specification": "pump-specification.pdf",
  "vendor": "vendor-a-submittal.pdf",
  "compliance_score": 50.0,
  "counts": {
    "PASS": 2,
    "DEVIATION": 1,
    "MISSING": 1,
    "REVIEW": 1
  },
  "findings": []
}
```

## Finding

A finding contains:

- original normalized requirement
- matched vendor fact, or `null`
- status
- matching confidence
- deterministic reason
- specification source page/line/section
- vendor source page/line

The source objects are retained so downstream systems do not need to reconstruct provenance from display text.

## Procurement integration

`supplier-scorecard` can consume `compliance_score` as its technical-compliance signal. The full finding list should be retained as the audit artifact rather than reducing the decision to a single number.

## Stability

v0.x contracts may evolve. Breaking schema changes should increment the payload `version` and be documented in `CHANGELOG.md`.
