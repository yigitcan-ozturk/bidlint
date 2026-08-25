# Supplier response readiness preflight

## Purpose

`bidlint-supplier-readiness` is a deterministic preflight for a supplier clarification response returned through the normal project communication channel.

It sits between the supplier's returned JSON and the buyer-side review workflow. Its job is to catch an unusable or incomplete return before evidence assessment and revision history are started.

It does **not** decide technical compliance, approve a supplier, accept a deviation, or alter the frozen BidLint evaluator.

## Command

```text
bidlint-supplier-readiness clarification-register.json supplier-response.json readiness.json
```

Exit status:

- `0`: response is ready to enter buyer review;
- `2`: response is structurally valid but one or more blocking readiness checks failed;
- command failure: the response cannot be bound to the clarification register or violates the response contract.

A readiness JSON report is written for both exit `0` and exit `2`.

## Blocking checks

The response is ready for buyer review only when all of these are true:

- responder name is present;
- responder company is present;
- supplier response is bound to the intended clarification register;
- every open clarification item contains either a non-empty technical supplier response or an offered value.

The underlying buyer-ingestion validator remains fail-closed for specification, vendor, requirement ID, category, parameter, prior finding status, duplicate IDs, missing IDs and unexpected IDs.

## Evidence references

Evidence-reference coverage is reported but is not a universal blocking condition at this stage.

A supplier may legitimately state that a certificate, test report or calculation will follow later. Whether evidence is required and whether it is adequate belongs to the explicit human evidence-adequacy workflow, not to this transport/readiness check.

The readiness report therefore exposes:

- total open items;
- responses present;
- evidence references present;
- unanswered requirement IDs;
- requirement IDs without evidence references;
- blocking failures;
- all individual checks;
- the same source provenance captured by buyer ingestion.

## Safety boundary

The readiness output always preserves:

- `automatic_acceptance = false`;
- `human_review_required = true`;
- `affects_evaluator = false`.

A `ready_for_buyer_review = true` result means only that the returned response is sufficiently complete to start human buyer review.

## External pilot use

For the current external supplier pilot, do not reissue an already dispatched form merely to gain this preflight feature. The preflight accepts the existing response contract and uses the same structural/source binding rules as buyer ingestion.

When the returned supplier JSON arrives, the recommended sequence is:

1. preserve the exact returned JSON bytes;
2. run `bidlint-supplier-readiness`;
3. if ready, run `bidlint-supplier-pilot prepare-return`;
4. complete and validate evidence assessment;
5. initialize or append immutable supplier history;
6. complete the pilot attestation;
7. execute the hosted-portal readiness gate.
