# supplier-scorecard technical-compliance contract

`bidlint` can export one deterministic technical-compliance result as a small JSON fragment compatible with the `technical_compliance` input used by `supplier-scorecard`.

The integration is deliberately one-way:

```text
specification + vendor evidence
            │
            ▼
          bidlint
            │
            ├── PASS / DEVIATION / MISSING / REVIEW audit
            │
            ▼
supplier-scorecard technical-compliance fragment
            │
            ▼
      supplier-scorecard
```

`supplier-scorecard` does not decide or alter bidlint findings. `bidlint` does not use commercial, price or vendor-risk signals to change technical compliance.

## Create a fragment

```bash
bidlint compare specification.pdf vendor-a.pdf \
  --supplier-name "Supplier A" \
  --scorecard-output supplier-a-technical.json
```

The normal bidlint report can be written at the same time:

```bash
bidlint compare specification.pdf vendor-a.pdf \
  --output supplier-a-compliance.json \
  --supplier-name "Supplier A" \
  --scorecard-output supplier-a-technical.json
```

Both `--supplier-name` and `--scorecard-output` are required together. The integration output must use a `.json` filename.

## Contract version 1

When every requirement is deterministically resolved as `PASS`, `DEVIATION` or `MISSING`, the fragment contains a numeric 0–100 signal:

```json
{
  "contract": "supplier-scorecard.technical-compliance",
  "contract_version": "1",
  "supplier": "Supplier A",
  "technical_compliance": 75.0,
  "technical_compliance_status": "READY",
  "technical_compliance_audit": {
    "tool": "bidlint",
    "version": "0.5.0.dev0",
    "specification": "specification.pdf",
    "vendor": "vendor-a.pdf",
    "compliance_score": 75.0,
    "counts": {
      "PASS": 3,
      "DEVIATION": 0,
      "MISSING": 1,
      "REVIEW": 0
    },
    "finding_count": 4,
    "review_requirement_ids": []
  }
}
```

The numeric value is the existing bidlint compliance score. No second scoring formula is introduced for the integration.

## REVIEW blocks the numeric signal

If any finding remains `REVIEW`, bidlint does **not** pass the partial deterministic score into supplier ranking:

```json
{
  "technical_compliance": null,
  "technical_compliance_status": "REVIEW_REQUIRED"
}
```

The audit still includes bidlint's partial `compliance_score`, counts and the IDs of requirements that require review. That partial score is diagnostic only; it is not the integration signal.

This matters because bidlint's normal compliance score deliberately excludes `REVIEW` findings from its denominator. Sending that partial score to a procurement ranking engine could make unresolved engineering evidence look more certain than it is.

## No requirements

When the report contains no requirements:

```json
{
  "technical_compliance": null,
  "technical_compliance_status": "NO_REQUIREMENTS"
}
```

No zero score is fabricated.

## supplier-scorecard compatibility

`supplier-scorecard` accepts an optional `technical_compliance` value between 0 and 100. When the field is absent or null, it falls back to its legacy three-component mode and re-normalizes the non-technical weights.

For a ready result, merge the fragment's technical signal into the corresponding supplier profile:

```json
{
  "supplier": "Supplier A",
  "payment_terms": "30 days",
  "technical_compliance": 75.0,
  "vendor_risk": {
    "on_time_delivery": 94,
    "defect_rate": 1.0,
    "compliance_incidents": 0,
    "dependency_share": 25
  }
}
```

For `REVIEW_REQUIRED` or `NO_REQUIREMENTS`, keep `technical_compliance` null or omit it so unresolved technical evidence does not influence automatic supplier ranking.

The complete bidlint fragment may also be retained as an input-side audit artifact. `supplier-scorecard` currently consumes the numeric `technical_compliance` field; bidlint's detailed findings remain in the normal bidlint report.

## Status semantics

| `technical_compliance_status` | Numeric signal | Meaning |
| --- | ---: | --- |
| `READY` | 0–100 | All findings are deterministically resolved |
| `REVIEW_REQUIRED` | `null` | At least one engineering finding requires review |
| `NO_REQUIREMENTS` | `null` | No requirements were available to score |

`DEVIATION` and `MISSING` do not suppress the signal. They are deterministic negative outcomes and are already reflected in the numeric compliance score.

## Design boundary

The contract intentionally does not:

- convert `REVIEW` into a guessed score
- let supplier-scorecard change bidlint technical findings
- mix price, commercial terms or vendor risk into technical compliance
- hide deviations or missing evidence from the audit record
- introduce a second technical scoring formula

The goal is a narrow, auditable hand-off between two deterministic tools.
