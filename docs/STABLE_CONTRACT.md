# BidLint 1.x stable compatibility contract

BidLint 1.0 freezes the public automation contract for the 1.x line. The machine-readable floor is exposed by `bidlint.contracts.stable_contract_manifest()` and guarded by regression tests.

## Versioning policy

BidLint follows semantic versioning for the stable 1.x line.

- **Patch** releases may fix bugs, parsing defects, packaging issues, security issues, and documentation without intentionally changing the public compatibility contract.
- **Minor** releases may add commands, options, JSON fields, model fields with defaults, formats, or workflow surfaces when existing 1.x consumers continue to work unchanged.
- **Major** releases may remove, rename, or semantically repurpose frozen contract elements.

Deprecations should be documented before removal and remain supported through the rest of the current major line unless a security issue makes that impossible.

## Frozen statuses and scoring

Compliance finding statuses are exactly:

`PASS`, `DEVIATION`, `MISSING`, `REVIEW`.

Knockout statuses are exactly:

`ELIGIBLE`, `REVIEW_REQUIRED`, `DISQUALIFIED`.

The compliance score is the percentage of `PASS` findings among `PASS + DEVIATION + MISSING`. `REVIEW` is excluded from the denominator. A report with no evaluable findings scores `0.0`. The published score is rounded to one decimal place.

These meanings cannot change within 1.x. New evaluation dimensions must be additive rather than silently changing existing status or score semantics.

## CLI contract

The following commands remain available throughout 1.x:

- `bidlint compare`
- `bidlint rank`
- `bidlint extract`

Additional commands may be added in a minor release. Existing command names and established option meanings must not be removed or repurposed in 1.x.

Public process exit codes are frozen:

| Code | Meaning |
| ---: | --- |
| 0 | success |
| 2 | usage error |
| 3 | input/document error |
| 4 | configuration/policy error |
| 5 | output or filesystem I/O error |
| 70 | unexpected internal error |

## Model compatibility floor

`SourceRef` retains `document`, `page`, `line`, and `section`.

`Requirement` retains `id`, `text`, `parameter`, `operator`, `value`, `unit`, `mandatory`, and `source`.

`VendorFact` retains `parameter`, `raw_value`, `value`, `unit`, and `source`.

`Finding` retains `requirement`, `vendor_fact`, `status`, `confidence`, and `reason`.

Minor versions may add optional/defaulted fields, but the frozen fields above cannot be removed, renamed, or assigned incompatible meanings within 1.x.

## Report JSON compatibility floor

A normal report keeps these top-level keys:

- `tool`
- `version`
- `specification`
- `vendor`
- `compliance_score`
- `counts`
- `findings`

`knockout` remains an additive optional key when knockout evaluation is active. Minor releases may add new optional keys. Existing required keys and their meanings remain stable through 1.x.

Consumers should treat `version` as package metadata rather than requiring an exact patch/minor value.

## Procurement boundary

The stable contract does not introduce commercial scoring, price preference, delivery preference, contractual acceptance, or implicit knockout inference. Existing procurement artifacts remain derived from explicit deterministic findings and explicit policy.
