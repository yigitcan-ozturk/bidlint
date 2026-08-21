# Production adoption

BidLint 1.1 moves beyond a stable software contract into repeatable production adoption. This document defines the pilot protocol used before a real procurement workflow is treated as validated.

## 1. Contract conformance before reruns

Archived JSON reports and downstream integration fixtures can be checked without rerunning extraction:

```bash
bidlint-contract report.json
```

For machine-readable output:

```bash
bidlint-contract report.json --json
```

To inspect the compatibility floor itself:

```bash
bidlint-contract --manifest
```

The checker validates the required BidLint 1.x report surface, including required report/model fields, finding status values, status-count consistency, deterministic compliance-score semantics and knockout status values. Unknown additive fields are intentionally accepted so a backward-compatible 1.x minor release can extend the payload.

Exit codes follow the public process contract where applicable: `0` for a conformant report, `3` for invalid/non-conformant input, `5` for I/O failure and argparse's `2` for invalid command usage.

## 2. Manifest-driven pilot runner

A sanitized pilot is described by a small strict JSON manifest and run with:

```bash
bidlint-pilot pilot.json --json --output pilot-evidence.json
```

A single vendor selects normal `compare` behavior; two or more vendors select normal `rank` behavior. The runner calls the existing BidLint CLI path rather than implementing a second evaluator.

Example:

```json
{
  "pilot_id": "pump-package-001",
  "specification": "sanitized/specification.pdf",
  "vendors": [
    "sanitized/vendor-a/",
    "sanitized/vendor-b/"
  ],
  "repeats": 2,
  "options": {
    "threshold": 0.52,
    "aliases": "policies/aliases.json",
    "knockouts": "policies/knockouts.json",
    "xlsx_sheet": null,
    "ifc_class": null,
    "ifc_guid": null,
    "ifc_pset": null
  }
}
```

Paths are resolved relative to the manifest file. `repeats` must be between 2 and 10 because the pilot runner exists to produce repeatability evidence, not merely execute one comparison.

The manifest accepts only technical execution settings already exposed by BidLint. Commercial price, payment terms, delivery preference, commercial scoring or contractual acceptance are rejected as unknown options rather than becoming hidden decision inputs.

### Pilot evidence output

For every run the runner records:

- pilot ID and compare/rank mode;
- repeat count;
- canonical SHA-256 digest of every JSON run;
- whether all run digests are identical;
- BidLint 1.x conformance result for every generated report;
- SHA-256 digest of the manifest content;
- SHA-256 digest of the actual specification, vendor files/directories and referenced aliases/knockout policy files;
- per-file corpus hashes without copying source document contents into the evidence JSON.

A pilot runner `PASS` therefore means **the supplied sanitized corpus produced repeatable and contract-conformant BidLint output**. It does not mean that a domain engineer has approved the technical decisions or that an external deployment has been validated.

Symlinked corpus roots/files are rejected so the evidence digest cannot silently refer to content outside the declared corpus tree.

## 3. Production pilot package standard

A pilot corpus must be reproducible without placing confidential customer documents in the public repository. Raw customer documents should remain outside the repository and outside benchmark workflows.

### Sanitization rules

Before a fixture may be committed or shared:

1. Remove company names, contact details, project addresses, customer identifiers and signatures.
2. Replace document metadata that can identify the originating project.
3. Preserve technical structure, units, table geometry and ambiguity patterns needed to reproduce parser behavior.
4. Replace commercially sensitive prices, lead times and contractual clauses with neutral placeholders unless they are specifically required for a non-commercial parser test.
5. Confirm that images, embedded files, comments, spreadsheet hidden content and PDF metadata do not retain sensitive information.
6. Record the sanitized fixture hash so repeated pilot runs can prove they used the same inputs.

## 4. Pilot acceptance checklist

A pilot is considered technically validated only when all applicable gates pass:

- every supported input completes or fails with the documented structured error contract;
- every compliance finding retains traceable specification evidence and vendor evidence when evidence exists;
- `bidlint-pilot` reports identical JSON output digests across repeated runs;
- every generated report passes BidLint 1.x conformance validation;
- `PASS / DEVIATION / MISSING / REVIEW` behavior agrees with the frozen 1.x semantics;
- known conflicting evidence becomes explicit review work rather than silent source selection;
- explicit knockout policy produces the expected procurement gate without inferred knockouts;
- clarification, deviation/review and procurement-readiness exports remain internally consistent;
- a domain reviewer checks all deviations, missing evidence, review items and knockout outcomes;
- any false positive or false negative is converted into a sanitized regression fixture before the pilot is closed.

A pilot is not considered successful merely because the process exits with code `0`, and a synthetic pilot cannot close the roadmap item requiring an external sanitized corpus.

## 5. Production-shaped profiling gate

The existing 20,000-fact benchmark remains a pure duplicate-consolidation regression test. BidLint 1.1 also profiles a workload that deliberately includes conflicting evidence and peak-memory tracking:

```bash
python benchmarks/production_profile.py
```

The CI workload uses 6,000 canonical parameters, four evidence documents per parameter and a deterministic conflict every 25 parameters. This exercises both the equivalent-evidence and explicit-review paths while measuring consolidation CPU time and Python allocation peak memory with `tracemalloc`.

The CI ceilings are deliberately broad regression tripwires, not service-level guarantees. Customer-document extraction time depends on PDF structure, workbook complexity and optional IFC runtimes and therefore must be measured separately during a real pilot.

## 6. Pilot evidence to retain

For each completed external pilot, retain internally:

- BidLint version and commit SHA;
- immutable `bidlint-pilot` evidence JSON;
- sanitized corpus and manifest SHA-256 digests;
- exact explicit selectors and policies;
- conformance result;
- benchmark/profile result from the same release line;
- human-reviewed false-positive and false-negative register;
- unresolved limitations and decision on whether each limitation blocks rollout.

The public repository should receive only sanitized regression cases and generic documentation derived from that evidence.

## 7. Adoption boundary

BidLint remains a deterministic technical compliance engine. Production adoption does not change these boundaries:

- no hidden commercial scoring;
- no automatic contractual acceptance;
- no inferred knockout criteria;
- no replacement for engineering or procurement approval;
- no claim that a synthetic benchmark is equivalent to real customer-document throughput.

The production goal is repeatable evidence, explicit uncertainty and auditable procurement hand-off.
