# Supplier clarification revision history

BidLint 1.2 preserves supplier clarification and evidence-review revisions as an immutable, hash-linked history. A later supplier answer never overwrites the earlier record.

This workflow remains outside the frozen BidLint 1.x evaluator. Revision comparison and conflict flags are buyer-side review signals only.

## Initialize history

Create the first explicit project revision from a buyer-side supplier clarification review:

```bash
bidlint-supplier-history init \
  buyer-review-r1.json \
  supplier-history.json \
  --revision-id R1
```

A validated supplier evidence review can be bound to the same revision:

```bash
bidlint-supplier-history init \
  buyer-review-r1.json \
  supplier-history.json \
  --revision-id R1 \
  --evidence-review evidence-review-r1.json
```

Revision IDs are supplied explicitly by the project workflow. BidLint does not invent dates or project revision labels.

## Append a superseding revision

A new supplier response is ingested and reviewed normally, then appended as a revision that explicitly supersedes the current active revision:

```bash
bidlint-supplier-history append \
  supplier-history.json \
  buyer-review-r2.json \
  supplier-history-r2.json \
  --revision-id R2 \
  --supersedes R1 \
  --evidence-review evidence-review-r2.json
```

Appending from a non-active revision is rejected. This prevents silent branching; a competing branch requires explicit human resolution before it becomes the active lineage.

## Integrity model

Every revision stores:

- explicit `revision_id` and sequence;
- `supersedes_revision_id`;
- SHA-256 of the parent revision;
- canonical and byte-level SHA-256 provenance for the supplier clarification review;
- optional canonical and byte-level SHA-256 provenance for the validated evidence review;
- normalized item snapshots;
- a canonical `revision_sha256` covering the revision content.

The history head stores the active revision ID and SHA-256. Any later mutation of a retained revision causes chain validation to fail.

Validate a retained history with:

```bash
bidlint-supplier-history validate supplier-history.json history-validation.json
```

## Change and conflict classification

For every requirement, a superseding revision is compared with the previous active revision and classified as:

- `ADDED`
- `REMOVED`
- `UNCHANGED`
- `CHANGED`
- `CONFLICT`

A normal response text, evidence-reference, comment, or evidence-assessment change is retained as `CHANGED` unless it creates a defined technical contradiction.

BidLint currently surfaces `CONFLICT` when both revisions contain non-empty but different core offered values or designations, or when requirement identity/status changes. The conflict record preserves previous/current values and sets `resolution_status = PENDING_REVIEW`.

BidLint does not select a winner. The newer revision may explicitly supersede the prior artifact in the project lineage, but contradictory technical values remain visible until a human resolves them.

## Evidence supersession

A validated `bidlint.supplier-evidence-review / 1` can be attached to a revision only when its provenance is cryptographically bound to that exact supplier clarification review. This prevents an evidence assessment from being silently reused against a different supplier response.

Evidence snapshots are retained in each revision. A newer assessment therefore supersedes by revision lineage rather than deleting historical certificate, test-basis, calculation, or supporting-document decisions.

## Evaluator boundary

The history contract explicitly states:

- `human_review_only = true`
- `affects_evaluator = false`

`CONFLICT`, `CHANGED`, or a newer evidence assessment does not modify BidLint PASS / DEVIATION / MISSING / REVIEW semantics, scoring, technical acceptance, commercial acceptance, or contractual status.
