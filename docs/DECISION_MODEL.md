# Decision model

`bidlint` separates **matching** from **evaluation**.

A lexical match does not mean a technical PASS. It only identifies the most likely offered parameter. The deterministic evaluator then decides whether the values can safely be compared.

## Finding states

### PASS
A matched numeric vendor value satisfies the parsed operator and required value.

### DEVIATION
A matched numeric vendor value violates the parsed operator and required value.

### MISSING
No vendor parameter exceeds the configurable matching threshold.

### REVIEW
The most likely parameter exists, but the comparison cannot be made safely and deterministically — for example qualitative text, unsupported units or non-numeric values.

## Compliance score

The v0.1 score is intentionally simple:

```text
PASS / (PASS + DEVIATION + MISSING) × 100
```

`REVIEW` findings are excluded from the numeric denominator because they are unresolved rather than known passes or failures. Their count remains visible and must be considered before approval.

This score is a technical-compliance signal, not an automatic procurement award decision.

## Portfolio ranking

`bidlint rank` sorts vendors by:

1. higher compliance score
2. fewer `DEVIATION + MISSING` findings
3. vendor filename for deterministic tie-breaking

Future policy profiles may add critical/mandatory requirements, but v0.1 does not hide category-specific assumptions inside the base engine.

## Matching confidence

Each finding stores a 0–1 matching confidence. Confidence describes **parameter similarity**, not decision correctness.

The default matching threshold is `0.52` and can be overridden from the CLI.
