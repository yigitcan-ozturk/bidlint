# Supplier response review

BidLint 1.2 keeps supplier clarification intake outside the frozen 1.x evaluator semantics. Supplier responses are evidence inputs for a buyer-side human review step; they never promote a finding to PASS or create contractual acceptance automatically.

## Flow

1. Export the stable clarification register.
2. Generate and send the offline supplier form with `bidlint-supplier-intake`.
3. Receive `bidlint-supplier-response.json` through the approved project channel.
4. Ingest the original register and returned response together:

```bash
bidlint-supplier-review \
  clarification-register.json \
  bidlint-supplier-response.json \
  buyer-review.json
```

The output contract is `bidlint.supplier-clarification-review / 1`.

## Fail-closed matching

Ingestion rejects:

- wrong response or register contracts/versions;
- specification or vendor mismatches;
- missing, duplicate or unexpected requirement IDs;
- changed category, parameter or prior finding status;
- malformed responder/response fields;
- a declared source-register SHA-256 that does not match the supplied register.

The current offline form contract from the first real pilot does not require a source-register digest. Those responses remain ingestible through structural binding: specification, vendor, requirement IDs, category, parameter and prior finding status must all match. Future forms may add the canonical register digest for a stronger binding without invalidating the first pilot.

## Provenance

The buyer review package records:

- canonical SHA-256 of the clarification register JSON;
- byte-level SHA-256 and byte length of the exact register file ingested;
- byte-level SHA-256 and byte length of the exact supplier response file ingested;
- source file names;
- the binding mechanism used to pair the response to the register.

This preserves the exact received artifact independently from JSON formatting and also gives a canonical digest for semantic register identity.

## Human-review boundary

Every ingested item is emitted with:

- `review_status = PENDING_REVIEW`;
- `human_review_required = true`;
- `automatic_acceptance = false` at package level.

`response_present` and `evidence_reference_present` are descriptive intake signals only. They are not compliance decisions and do not modify the deterministic evaluator.

## Next productization step

Evidence adequacy will be modeled separately for calculations, material/test certificates, test basis, drawings and other supporting documents. Revision and conflict handling will then layer on top of the immutable response provenance rather than rewriting prior supplier evidence.
