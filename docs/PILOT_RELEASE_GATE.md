# External pilot release gate

BidLint 1.1 keeps the external-pilot release decision explicit. A successful process exit, a clear automated sanitization scan, or a deterministic pilot run is not enough on its own to approve a release.

Use the private workspace created by `bidlint-pilot-init` and retain these local-only files:

```text
pilot-workspace/
├── pilot.json
├── evidence/
│   ├── sanitization-scan.json
│   ├── approved-baseline.json
│   └── replay-evidence.json
└── review/
    ├── TECHNICAL_REVIEW.md
    └── approval.json
```

`evidence/` and `review/` are git-ignored by default.

## Sequence

1. Sanitize the real external corpus and run:

```bash
bidlint-pilot-scan pilot.json --json --output evidence/sanitization-scan.json
```

2. Resolve every automated blocker and manually inspect every remaining REVIEW coverage gap.

3. Run the successful pilot candidate and retain it as the approved baseline only after domain review:

```bash
bidlint-pilot pilot.json --json --output evidence/approved-baseline.json
```

4. Complete `review/TECHNICAL_REVIEW.md` and explicitly update `review/approval.json`. The generated JSON template starts in a blocked state; BidLint never infers human approval from Markdown checkboxes or process exit codes.

5. Run the same sanitized corpus again and retain fresh replay evidence:

```bash
bidlint-pilot pilot.json --json --output evidence/replay-evidence.json
```

6. Verify the immutable baseline replay:

```bash
bidlint-pilot-verify evidence/approved-baseline.json evidence/replay-evidence.json
```

7. Evaluate the complete release gate:

```bash
bidlint-pilot-gate .
```

For machine-readable output:

```bash
bidlint-pilot-gate . --json
```

## What the gate requires

The gate returns `RELEASE READY` only when all of the following are true:

- the sanitization result was produced by `bidlint-pilot-scan` for the same pilot ID;
- `automated_clear` is true and `blocker_count` is zero;
- explicit human sanitization approval is present with reviewer and ISO review date;
- all sanitization REVIEW findings are explicitly recorded as resolved;
- baseline and replay evidence are successful BidLint pilot evidence for the same pilot;
- the baseline replay verifier reports an exact compatibility match for pilot ID, mode, report count, manifest digest, corpus digest and output digest;
- the technical reviewer explicitly selects `APPROVE_BASELINE`;
- every non-PASS technical finding was reviewed;
- unresolved limitation count is zero;
- every known product defect has a corresponding minimized regression fixture/test count;
- knockout criteria remained explicit rather than inferred;
- no commercial scoring was introduced.

The command returns exit code `0` only when the release gate is ready, `3` for a blocked/invalid gate, `5` for I/O failures and argparse's `2` for invalid usage.

## Human review record

`review/approval.json` is intentionally explicit. Its default state created by `bidlint-pilot-init` is not approved:

```json
{
  "tool": "bidlint-pilot-review",
  "pilot_id": "external-pilot-001",
  "sanitization": {
    "approved": false,
    "reviewer": "",
    "reviewed_at": "",
    "review_findings_resolved": false
  },
  "technical": {
    "decision": "RE_RUN_AFTER_FIXES",
    "reviewer": "",
    "reviewed_at": "",
    "all_non_pass_findings_reviewed": false,
    "false_positive_count": 0,
    "false_negative_count": 0,
    "unresolved_limitation_count": 0,
    "known_product_defect_count": 0,
    "regression_fixtures_created": 0,
    "explicit_knockouts_only": true,
    "no_commercial_scoring": true
  }
}
```

A human must deliberately update the review record after reviewing the sanitized sources and BidLint findings. The gate validates the record; it does not create or approve it.

## Boundary

This gate does not make a contractual award decision, infer knockout criteria, score price/delivery, or replace engineering/procurement approval. It only establishes whether the documented BidLint 1.1 external-pilot evidence package is internally complete enough to unblock a software release decision.
