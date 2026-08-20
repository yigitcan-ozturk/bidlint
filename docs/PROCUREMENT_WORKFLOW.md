# Procurement workflow

`v0.8.0.dev0` adds explicit procurement workflow artifacts on top of bidlint's deterministic technical findings.

The core evaluator still produces only `PASS / DEVIATION / MISSING / REVIEW`. Procurement artifacts consume those findings without rewriting them.

## Output surfaces

Single-vendor comparison:

```bash
bidlint compare specification.pdf Supplier-A/ \
  --knockouts knockouts.json \
  --clarifications-output supplier-a-clarifications.json \
  --deviations-output supplier-a-review-register.json \
  --procurement-output supplier-a-readiness.json
```

Multi-vendor ranking:

```bash
bidlint rank specification.pdf Supplier-A/ Supplier-B/ \
  --knockouts knockouts.json \
  --clarifications-output clarifications.json \
  --deviations-output review-register.json \
  --procurement-output procurement-ranking.json
```

All procurement workflow outputs are JSON-only in this development slice.

## Bidder clarification and unanswered requirement register

Contract: `bidlint.procurement-clarifications` version `1`.

Finding mapping is deterministic:

| Finding | Procurement artifact |
| --- | --- |
| `PASS` | no clarification record |
| `REVIEW` | bidder clarification |
| `MISSING` | unanswered requirement |
| `DEVIATION` | handled by the deviation register |

Each record retains requirement text, confidence, evaluator reason, specification provenance, and vendor evidence provenance when evidence exists.

The question text is generated from a fixed template. No model-generated procurement language is introduced.

The portfolio contract is `bidlint.procurement-clarifications-portfolio` version `1`. Vendor order follows CLI input order rather than technical ranking order.

## Deviation register and internal review queue

Contract: `bidlint.procurement-review-register` version `1`.

- `DEVIATION` findings enter `deviations`.
- `REVIEW` findings enter `review_queue`.
- `MISSING` findings remain in the unanswered requirement register.

A `REVIEW` finding therefore has two intentional workflow views:

1. bidder-facing clarification, when further supplier evidence is needed;
2. internal technical review, because the evaluator cannot safely close the requirement.

If a finding is also an explicit knockout criterion, the register adds `knockout_criterion: true`. This is audit context only; the register does not create a new compliance or knockout decision.

## Procurement readiness

Contract: `bidlint.procurement-readiness` version `1`.

Readiness is deliberately stricter than ordinary technical ranking:

| Status | Meaning |
| --- | --- |
| `READY` | explicit knockout policy applied, knockout gate eligible, and no deviation/missing/review remains |
| `ACTION_REQUIRED` | open deviation or unanswered requirement remains |
| `REVIEW_REQUIRED` | technical or knockout review remains unresolved |
| `POLICY_REQUIRED` | no explicit knockout policy has been applied |
| `DISQUALIFIED` | explicit knockout gate is disqualified |

An empty report is `ACTION_REQUIRED`.

### Ready-only portfolio ranking

Contract: `bidlint.procurement-readiness-portfolio` version `1`.

Only `READY` suppliers receive a procurement rank. Suppliers in `ACTION_REQUIRED`, `REVIEW_REQUIRED`, `POLICY_REQUIRED`, or `DISQUALIFIED` states are listed under `excluded` with reasons and **do not receive a numeric rank**.

This avoids turning an unresolved or disqualified supplier into an apparent second- or third-choice purchasing recommendation.

Within the ready set, ordering remains deterministic using the existing technical score/tie-break logic.

## Supplier-scorecard hand-off

The existing `supplier-scorecard.technical-compliance` contract version `1` remains backward compatible.

Version `1` still rejects knockout-assessed reports because it predates procurement gates.

A procurement-aware contract version `2` is available explicitly:

```bash
bidlint compare specification.pdf Supplier-A/ \
  --knockouts knockouts.json \
  --scorecard-output supplier-a-scorecard.json \
  --supplier-name "Supplier A" \
  --scorecard-contract 2
```

Contract version `2` publishes numeric `technical_compliance` only when procurement readiness is `READY`.

For every other readiness status the numeric signal is `null`, while the raw compliance score, counts, knockout state, and procurement reasons remain in the audit payload.

This prevents downstream supplier ranking from using a technically unresolved score as if it were procurement-ready.

## Compatibility boundaries

- normal compliance JSON is unchanged by clarification/deviation/readiness exports;
- knockout data remains additive and opt-in;
- procurement exports never rewrite finding statuses;
- no commercial price, delivery, payment-term, or contractual scoring is inferred;
- no specification sentence becomes a knockout automatically;
- no unresolved supplier receives a ready-only procurement rank.

The operating rule remains: **explicit evidence, explicit policy, explicit unresolved work**.
