# Supplier evidence adequacy

BidLint 1.2 treats supplier clarification responses as inputs to an explicit buyer-side human review workflow. Evidence adequacy is intentionally separate from the frozen BidLint 1.x evaluator: it does not change PASS / DEVIATION / MISSING / REVIEW, scoring, or contractual acceptance.

## Workflow

First create an assessment template from the buyer-side supplier review produced by `bidlint-supplier-review`:

```bash
bidlint-supplier-evidence template \
  buyer-review.json \
  supplier-evidence-assessment.json
```

A technical reviewer completes the generated JSON and records which evidence types are required, their current adequacy, references, and rationale.

Then validate the completed assessment against the exact source review:

```bash
bidlint-supplier-evidence validate \
  buyer-review.json \
  supplier-evidence-assessment.json \
  supplier-evidence-review.json
```

The validated output contract is `bidlint.supplier-evidence-review / 1`.

## Evidence dimensions

Each clarification item contains exactly four explicit evidence dimensions:

- `calculation`
- `certificate`
- `test_basis`
- `supporting_document`

For each dimension, `required` is one of:

- `UNKNOWN`
- `REQUIRED`
- `NOT_REQUIRED`

The evidence `status` is one of:

- `NOT_ASSESSED`
- `MISSING`
- `PARTIAL`
- `ADEQUATE`
- `NOT_REQUIRED`

The reviewer also assigns an item-level `overall` value from:

- `NOT_ASSESSED`
- `INADEQUATE`
- `PARTIAL`
- `ADEQUATE`
- `NEEDS_CLARIFICATION`

## Fail-closed consistency rules

The validator rejects structurally inconsistent assessments, including:

- a source-review digest that does not match the buyer review;
- missing, duplicate, unexpected, or identity-mutated requirement items;
- an evidence dimension marked `ADEQUATE` or `PARTIAL` without a reference;
- `NOT_REQUIRED` status without an explicit `required=NOT_REQUIRED` decision;
- an item marked overall `ADEQUATE` while a required evidence dimension is not `ADEQUATE`;
- an item marked overall `ADEQUATE` while any evidence requirement remains `UNKNOWN`.

These are validation rules for a human assessment record, not new compliance-evaluator semantics.

## Provenance and decision boundary

The assessment template is bound to the source `bidlint.supplier-clarification-review` by canonical SHA-256. The validated output additionally records byte-level SHA-256 and byte length for the exact buyer-review and completed-assessment files.

Every validated package states:

- `human_review_only = true`
- `affects_evaluator = false`

Therefore an `ADEQUATE` evidence assessment means only that a buyer-side reviewer has recorded the evidence as adequate for the clarification-review workflow. It does not automatically produce BidLint `PASS`, approve a supplier, waive a deviation, or create contractual acceptance.

## Revision handling

Evidence assessments are designed to be retained as immutable reviewed artifacts. The next v1.2 productization layer will add revision lineage and explicit conflict detection so that later supplier answers or supporting documents supersede prior revisions by reference rather than overwriting historical evidence.
