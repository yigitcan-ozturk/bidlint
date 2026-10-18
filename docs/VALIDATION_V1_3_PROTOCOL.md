# BidLint v1.3 — Independent Validation Protocol

Status: DRAFT / NOT YET VALIDATED
Baseline: v1.2.1 (frozen 1.x decision semantics)
Lane: `validation/v1.3-independent-evidence`

## Objective
Independently assess whether BidLint's evidence-backed technical bid decisions are correct, reproducible and auditable on non-confidential examples. No changes to PASS / DEVIATION / MISSING / REVIEW semantics or scoring are authorized by this protocol.

## Corpus and provenance
Each case must have a stable case ID, source type (public, consented, or synthetic), source URL/license or consent record when applicable, SHA-256 for each input, collection date, expected outcome, reviewer rationale and evidence locator. Never commit confidential supplier documents or personal information. Keep real and synthetic results separate.

## Required strata
- Numeric compliance, including exact boundary and units conversion
- Explicit numeric deviation and incompatible units
- Missing vendor evidence
- Qualitative or ambiguous language requiring REVIEW
- Conflicting statements across supplier documents
- PDF extraction failure or unsupported document content
- XLSX sheet selection and formula/value ambiguity
- IFC optional-path behavior
- Supplier clarification and legacy response compatibility
- Repeated runs and document ordering permutations

## Execution
1. Freeze and record commit SHA, Python version, installed dependency versions and test environment.
2. Run existing package, CLI and regression tests before evaluating new cases.
3. Have an independent reviewer label each case without seeing BidLint's output.
4. Execute each case at least twice with identical inputs and compare canonical output bytes or normalized stable fields; record nondeterministic metadata separately.
5. Compare actual against expected PASS / DEVIATION / MISSING / REVIEW; classify every disagreement.
6. Audit evidence locators against source files; a correct status with fabricated or unsupported evidence is a failure.
7. Run negative controls for missing, malformed and conflicting evidence; fail closed to REVIEW or an explicit documented error rather than manufacturing PASS.
8. Report outcomes per stratum and per source type. Do not pool synthetic results into real-world claims.

## Release gates (proposed; not yet passed)
- 100% existing regression suite passing on supported Python versions.
- Zero fabricated PASS decisions in the reviewed corpus.
- Zero unsupported evidence citations in the reviewed corpus.
- 100% repeatability for stable output fields on identical inputs.
- All deviations and known limitations documented with reproducible case IDs.
- Any changes to stable 1.x behavior require separate explicit approval.

## Results template
| Case ID | Source type | Expected | Actual | Evidence verified | Repeatable | Reviewer notes |
| --- | --- | --- | --- | --- | --- | --- |
| PENDING | PENDING | PENDING | NOT RUN | NOT RUN | NOT RUN | Awaiting corpus |

No tests have been executed by creating this document. A passing release gate must be supported by stored run logs and corpus manifests.
