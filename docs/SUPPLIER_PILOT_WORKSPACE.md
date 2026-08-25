# Supplier Pilot Workspace Status

BidLint v1.2 uses an offline, artifact-bound supplier clarification workflow. As the pilot progresses, the workspace accumulates buyer review, evidence, history, attestation and portal-gate artifacts. `bidlint-supplier-pilot status` verifies that chain and reports the next safe operator action.

Run:

```text
bidlint-supplier-pilot status pilot-return workspace-status.json
```

The command is read-only with respect to the pilot workspace. It writes a `bidlint.supplier-workspace-status / 1` report to the requested output path.

## Standard workspace filenames

The status command recognizes these project-local filenames:

```text
pilot-return/
  pilot-return-manifest.json
  buyer-review.json
  evidence-assessment.json
  evidence-files.json        # optional; present for file-backed supplier evidence
  evidence-review.json       # created after human evidence validation
  supplier-history.json      # immutable revision history
  pilot-attestation.json     # completed external-pilot attestation
  portal-readiness.json      # deterministic portal gate result
```

`pilot-return-manifest.json`, `buyer-review.json`, and `evidence-assessment.json` are created by `prepare-return`. `evidence-files.json` is also created when `prepare-return` receives `--evidence-map`.

## Stages

The status contract may report:

- `AWAITING_EVIDENCE_REVIEW` — the returned supplier response is prepared but buyer evidence review has not been recorded.
- `EVIDENCE_REVIEW_INCOMPLETE` — an evidence review exists but required human completion is still missing.
- `AWAITING_HISTORY` — evidence review is complete; create the immutable supplier revision history.
- `AWAITING_ATTESTATION` — history is valid; create and complete the external-pilot attestation.
- `ATTESTATION_INCOMPLETE` — attestation exists but one or more real-pilot gate facts are not complete.
- `AWAITING_PORTAL_GATE` — the attestation is sufficient to execute the deterministic portal gate.
- `PORTAL_GATE_EVALUATED` — `portal-readiness.json` exactly reproduces from the current bound artifacts.

The output includes a `next_action` field with the next safe operator step. A stage is workflow state only; it is not technical compliance or supplier acceptance.

## Fail-closed verification

Status re-verifies the workspace instead of trusting filenames alone. It checks:

- pilot-return contract/version;
- buyer-review and evidence-assessment canonical/byte hashes against the pilot-return manifest;
- evidence-file manifest structure, exact digest and file count when present;
- buyer-review binding of the human evidence review;
- file-backed evidence manifest binding when `file:Fxxx` references are used;
- immutable supplier history validity and active buyer-review binding;
- pilot attestation artifact binding;
- deterministic reproducibility of `portal-readiness.json` from the current workspace.

If a bound artifact is edited, replaced, moved outside the workspace naming contract, or no longer reproduces the expected gate result, status fails instead of advancing the workflow.

## Product boundary

`bidlint-supplier-pilot status` has:

- `automatic_acceptance=false`
- `automatic_portal_approval=false`
- `human_review_required=true`
- `affects_evaluator=false`

It does not alter BidLint 1.x evaluator semantics, approve evidence, approve a supplier, accept a deviation, or authorize a hosted portal build.
