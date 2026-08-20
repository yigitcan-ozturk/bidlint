# Technical knockout criteria

`v0.8.0.dev0` adds an explicit procurement gate on top of bidlint's existing deterministic compliance findings.

Knockout evaluation does **not** replace `PASS / DEVIATION / MISSING / REVIEW`. It consumes selected requirement findings after the normal comparison has completed.

## Explicit policy

Knockouts are opt-in and identified by exact requirement IDs:

```json
{
  "requirement_ids": ["R0003", "R0007"]
}
```

Use the same policy for one supplier:

```bash
bidlint compare specification.pdf Supplier-A/ --knockouts knockouts.json
```

Or for all suppliers in a ranking run:

```bash
bidlint rank specification.pdf Supplier-A/ Supplier-B/ --knockouts knockouts.json
```

The policy parser is deliberately strict. The JSON document must contain only `requirement_ids`; the value must be a non-empty array of unique, non-empty strings. IDs that do not exist in the parsed specification are rejected before vendor evaluation.

## Gate semantics

Each selected requirement keeps its ordinary compliance finding. The procurement gate is derived from those findings:

| Finding | Knockout effect |
| --- | --- |
| `PASS` | criterion passes |
| `REVIEW` | gate becomes `REVIEW_REQUIRED` unless a failure also exists |
| `DEVIATION` | gate becomes `DISQUALIFIED` |
| `MISSING` | gate becomes `DISQUALIFIED` |

The report-level gate is one of:

- `ELIGIBLE` — every selected criterion is `PASS`
- `REVIEW_REQUIRED` — at least one selected criterion is `REVIEW` and none is `DEVIATION` or `MISSING`
- `DISQUALIFIED` — at least one selected criterion is `DEVIATION` or `MISSING`

Failure takes precedence over review. A `REVIEW` finding never becomes an automatic rejection.

## No implicit knockouts

`Requirement.mandatory` remains extraction metadata. A sentence containing `shall`, `must`, or `required` is **not** automatically treated as a procurement knockout.

This boundary is intentional: bidlint will not infer that every normative technical requirement is grounds for supplier disqualification. The procurement team must select knockout IDs explicitly.

## Ranking

When knockout policy is active for a ranking run, all vendor reports are assessed with the same policy. Ordering is deterministic:

1. `ELIGIBLE`
2. `REVIEW_REQUIRED`
3. `DISQUALIFIED`
4. existing compliance score and technical tie-break rules within each gate

Knockout-assessed and unassessed reports cannot be mixed in one ranking call.

Without `--knockouts`, the stable v0.7 ranking behavior is unchanged.

## JSON audit

When knockout evaluation is active, a single report gains an additive `knockout` object:

```json
{
  "status": "DISQUALIFIED",
  "requirement_ids": ["R0003", "R0007"],
  "failed_requirement_ids": ["R0007"],
  "review_requirement_ids": [],
  "criteria": [
    {
      "requirement_id": "R0003",
      "parameter": "motor efficiency",
      "finding_status": "PASS",
      "reason": "..."
    }
  ]
}
```

Portfolio JSON also adds `knockout_status` to each ranking entry when the gate is active. With no knockout policy, these fields are omitted so the existing report contract remains additive and backward-compatible.

## Procurement workflow integration

Knockout state is now consumed by the v0.8 procurement workflow:

- clarification and unanswered requirement register;
- deviation register and internal review queue;
- procurement readiness and ready-only ranking;
- supplier-scorecard technical-compliance contract version `2`.

The existing supplier-scorecard contract version `1` remains unchanged and still rejects knockout-assessed reports.

See [`PROCUREMENT_WORKFLOW.md`](PROCUREMENT_WORKFLOW.md).

## Deliberate limits

The procurement workflow still does not infer:

- commercial scoring;
- price or delivery preference;
- contractual acceptance;
- automatic knockout criteria from specification language.

The rule remains: **explicit evidence, explicit policy, no hidden disqualification logic**.
