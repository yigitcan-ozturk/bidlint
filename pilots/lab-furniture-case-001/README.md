# Lab Furniture Case 001 — Blind Evaluation Pilot

Status: ACTIVE PILOT

## Purpose

Validate BidLint against a real multi-document laboratory / technical-furniture procurement case while preserving supplier confidentiality and the frozen BidLint 1.x evaluator semantics.

This pilot is intentionally identity-blind during evaluation. Customer and supplier names, logos, contact data, tax identifiers, SharePoint links, project-specific identifiers and raw commercial documents are not committed to this repository.

## Product boundary

This pilot MUST NOT modify or reinterpret the frozen BidLint 1.x evaluator semantics:

- PASS
- DEVIATION
- MISSING
- REVIEW
- existing compliance scoring
- explicit knockout handling

The pilot MUST NOT create automatic contractual acceptance, automatic supplier approval, inferred knockout criteria, or hidden commercial scoring inside the 1.x evaluator.

Commercial normalization, material-fit analysis and award recommendation are separate pilot artifacts/workflows and remain human-reviewable.

## Privacy model

### Evidence vault

Original customer and supplier files remain outside the repository in their controlled source location.

### Blind workspace

Supplier identities are represented only as:

- Supplier-A
- Supplier-B
- Supplier-C
- Supplier-D

Customer identity is represented as:

- Customer-01

### Demo / portfolio

Only synthetic or further anonymized data may be used. Real prices must be replaced by indexed values or fabricated demo values.

## Input roles

The live case contains four source roles:

1. layout / furniture requirement drawing,
2. detailed supplier quotation,
3. legacy comparison spreadsheet,
4. technical presentation / material and supplier research.

The raw source files are not stored in GitHub.

## Pilot workflow

1. Freeze source set and compute provenance.
2. Redact / pseudonymize customer and supplier identities.
3. Extract a canonical requirement register from layout and technical documentation.
4. Bind quote line items to requirement / asset IDs.
5. Run technical compliance with unchanged 1.x semantics.
6. Build a separate commercial-normalization record:
   - quoted amount,
   - taxes,
   - transport,
   - installation,
   - exclusions,
   - unpriced scope,
   - payment / validity / delivery terms,
   - normalization confidence.
7. Build a separate material-fit record by use case rather than brand preference.
8. Generate supplier clarification items for missing, partial or conflicting evidence.
9. Process supplier responses through the existing v1.2 supplier collaboration workflow.
10. Freeze blind scores / findings before identity reveal.
11. Perform controlled identity reveal for the buyer-only decision package.
12. Produce a human-reviewed award recommendation and alternative scenario.

## Canonical entities

### Asset / requirement

Each item should receive a stable pilot identifier such as:

- LF-REQ-0001
- LF-ASSET-0001

Source-native layout codes may be retained only in buyer-controlled provenance, not public demo data.

### Supplier offer

Each supplier offer receives a stable blind identifier and immutable revision lineage.

### Clarification

Clarifications use deterministic IDs and remain bound to the exact requirement, supplier revision and evidence provenance.

## Material-fit dimensions

Material recommendations are evaluated by use case, including:

- chemical exposure,
- heat exposure,
- abrasion / scratch exposure,
- impact exposure,
- water / wet-area exposure,
- hygiene / cleanability,
- vibration sensitivity,
- cutout / serviceability needs,
- reparability / replaceability,
- lifecycle cost,
- visual / sample-review requirements.

The pilot must distinguish ordinary decorative porcelain slab from laboratory-grade technical ceramic / stoneware where evidence supports that distinction.

## Commercial-normalization dimensions

Commercial comparison is separate from 1.x compliance semantics and records at minimum:

- quoted subtotal,
- tax treatment,
- included logistics,
- included installation,
- utility / MEP exclusions,
- ventilation / ducting exclusions,
- missing priced scope,
- optional items,
- warranty,
- delivery lead time,
- offer validity,
- payment terms,
- normalization confidence,
- total-cost completeness state.

## Blind evaluation rule

Supplier identity must not be revealed to the evaluation view until the blind evaluation checkpoint is frozen.

Checkpoint:

`BLIND_SCORE_FREEZE_001`

After freeze, buyer-only mapping may reveal the supplier identities for negotiation and award.

## Pilot outputs

Required outputs:

1. source inventory + provenance manifest,
2. anonymization manifest,
3. canonical requirement register,
4. layout-to-BOQ binding table,
5. technical compliance matrix,
6. commercial normalization matrix,
7. material-fit matrix,
8. clarification register,
9. supplier response / evidence review package,
10. blind evaluation freeze artifact,
11. buyer-only identity reveal mapping,
12. award recommendation package,
13. fully anonymized demo case.

## Acceptance criteria

Pilot is successful only when:

- every recommendation is traceable to evidence or explicitly marked uncertain,
- no supplier wins because of brand identity,
- exclusions and unpriced scope cannot masquerade as savings,
- missing evidence produces clarification instead of guessed compliance,
- revisions never overwrite prior evidence,
- material choice is asset/use-case specific,
- blind results are frozen before identity reveal,
- external/demo artifacts contain no customer or supplier identifying data,
- existing BidLint 1.x evaluator semantics remain unchanged.

## Current known edge case

The live source set includes a legacy `.xls` comparison workbook. Native extraction is not yet guaranteed by the current pilot ingestion path. Treat this as an ingestion compatibility case; do not silently infer its contents. The rest of the pilot may proceed while this source remains pending conversion/extraction.
