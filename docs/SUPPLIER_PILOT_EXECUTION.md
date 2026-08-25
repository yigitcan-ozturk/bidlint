# External supplier pilot execution

BidLint `1.2.0.dev0` keeps supplier collaboration offline-first. The external pilot must prove the supplier interaction and buyer review workflow before hosted portal scope is reconsidered.

This workflow does not change the frozen BidLint 1.x evaluator, scoring, PASS / DEVIATION / MISSING / REVIEW semantics, supplier acceptance, or contractual status.

## 1. Receive the returned supplier response

When the supplier returns `bidlint-supplier-response.json`, keep the exact returned file. Do not copy values manually into a new JSON document.

Run:

```bash
bidlint-supplier-pilot prepare-return \
  clarifications.json \
  bidlint-supplier-response.json \
  pilot-return-001
```

The output directory is deliberately required to be new. BidLint writes:

- `buyer-review.json` — fail-closed response ingestion with exact returned-response byte provenance;
- `evidence-assessment.json` — editable human evidence-assessment template;
- `pilot-return-manifest.json` — hashes and the next required buyer action.

The generated buyer review remains `PENDING_REVIEW`, with `automatic_acceptance=false` and `human_review_required=true`.

## 2. Complete evidence assessment

A buyer-side technical reviewer completes the evidence assessment using the existing evidence model for:

- calculation;
- certificate;
- test basis;
- supporting document.

Validate it with:

```bash
bidlint-supplier-evidence validate \
  pilot-return-001/buyer-review.json \
  pilot-return-001/evidence-assessment.json \
  pilot-return-001/evidence-review.json
```

`ADEQUATE` is an evidence-review state only. It does not create BidLint PASS or supplier approval.

## 3. Create immutable supplier history

For the first returned response:

```bash
bidlint-supplier-history init \
  pilot-return-001/buyer-review.json \
  pilot-return-001/history.json \
  --revision-id SUPPLIER-R1 \
  --evidence-review pilot-return-001/evidence-review.json
```

If the supplier later corrects or revises the response, ingest the new response first and then append a new history revision. Never overwrite the prior revision.

## 4. Create the real-interaction attestation

After buyer review and history are complete, generate an artifact-bound attestation template:

```bash
bidlint-supplier-pilot attestation-template \
  pilot-return-001/buyer-review.json \
  pilot-return-001/evidence-review.json \
  pilot-return-001/history.json \
  pilot-return-001/pilot-attestation.json
```

The template contains canonical SHA-256 bindings to all three reviewed artifacts. The reviewer then records only observable external-pilot facts:

- a real external supplier response was received;
- whether the supplier completed the form without guided data re-entry;
- the normal project channel through which the response returned;
- whether usability feedback was recorded, plus a concise summary;
- whether a supplier revision occurred;
- reviewer identity.

Do not mark a statement true unless it actually occurred.

## 5. Evaluate the hosted-portal readiness gate

Run:

```bash
bidlint-supplier-pilot portal-gate \
  pilot-return-001/buyer-review.json \
  pilot-return-001/evidence-review.json \
  pilot-return-001/history.json \
  pilot-return-001/pilot-attestation.json \
  pilot-return-001/portal-readiness.json
```

The gate verifies:

1. real supplier-response byte provenance exists;
2. clarification-register binding was verified during ingestion;
3. the evidence review is bound to the exact buyer review and every requirement is represented;
4. evidence assessment has been completed by a named reviewer;
5. immutable revision history is valid and its active revision is bound to the current buyer review;
6. a revision is represented by at least two history revisions if the reviewer says a revision occurred;
7. supplier completion behavior, return channel and usability feedback are explicitly attested;
8. the attestation itself is bound to the exact review/evidence/history artifacts.

## Gate result

If any real-pilot condition is missing:

```json
{
  "ready_for_portal_reconsideration": false,
  "portal_decision": "DEFERRED"
}
```

If every gate condition is satisfied:

```json
{
  "ready_for_portal_reconsideration": true,
  "portal_decision": "RECONSIDER_SCOPE",
  "automatic_portal_approval": false
}
```

`RECONSIDER_SCOPE` does **not** mean “build the portal”. It means there is now enough real external workflow evidence to reopen the product-scope decision described in `SUPPLIER_PORTAL_DECISION.md`.

## Current live pilot

The ASTM A182 F317L supplier form already dispatched externally remains valid. It predates the optional source-register digest but is supported by the fail-closed structural binding in buyer-side ingestion. The live form should not be reissued solely because this execution gate was added.

Until an actual supplier response is returned and processed through this workflow, the hosted portal decision remains **DEFERRED**.
