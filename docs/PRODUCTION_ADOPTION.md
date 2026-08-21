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

The checker validates the required BidLint 1.x report surface, including:

- required top-level report keys;
- BidLint 1.x version identity;
- finding status values;
- required Requirement / VendorFact / Finding fields;
- status counts against the actual finding list;
- deterministic compliance-score semantics;
- knockout status values when a knockout assessment is present.

Unknown additive fields are intentionally accepted. A 1.x minor release may extend the payload without making older required fields invalid.

Exit codes follow the existing public process contract where applicable: `0` for a conformant report, `3` for an invalid/non-conformant input report, `5` for an I/O failure, and argparse's `2` for invalid command usage.

## 2. Production pilot package standard

A pilot corpus must be reproducible without placing confidential customer documents in the public repository.

Each pilot should have an internal manifest containing at least:

```json
{
  "pilot_id": "pump-package-001",
  "domain": "mechanical",
  "specification": "sanitized/specification.pdf",
  "vendors": [
    "sanitized/vendor-a/",
    "sanitized/vendor-b/"
  ],
  "selectors": {
    "xlsx_sheet": null,
    "ifc_class": null,
    "ifc_guid": null,
    "ifc_pset": null
  },
  "expected": {
    "requires_human_review": true,
    "known_knockout_ids": [],
    "known_unanswered_requirement_ids": []
  }
}
```

The manifest is project evidence, not a hidden scoring configuration. Commercial price, payment terms, delivery preference, contractual acceptance, or automatic disqualification rules do not belong in it.

### Sanitization rules

Before a fixture may be committed or shared:

1. Remove company names, contact details, project addresses, customer identifiers and signatures.
2. Replace document metadata that can identify the originating project.
3. Preserve technical structure, units, table geometry and ambiguity patterns needed to reproduce parser behavior.
4. Replace commercially sensitive prices, lead times and contractual clauses with neutral placeholders unless they are specifically required for a non-commercial parser test.
5. Confirm that images, embedded files, comments, spreadsheet hidden content and PDF metadata do not retain sensitive information.
6. Record the sanitized fixture hash so repeated pilot runs can prove they used the same inputs.

Raw customer documents should remain outside the repository and outside benchmark workflows.

## 3. Pilot acceptance checklist

A pilot is considered technically validated only when all applicable gates pass:

- every supported input completes or fails with the documented structured error contract;
- every compliance finding retains traceable specification evidence and vendor evidence when evidence exists;
- repeated runs over identical sanitized inputs produce identical JSON decisions;
- `PASS / DEVIATION / MISSING / REVIEW` behavior agrees with the frozen 1.x semantics;
- known conflicting evidence becomes explicit review work rather than silent source selection;
- explicit knockout policy produces the expected procurement gate without inferred knockouts;
- clarification, deviation/review and procurement-readiness exports remain internally consistent;
- produced report JSON passes `bidlint-contract` conformance validation;
- a domain reviewer checks all deviations, missing evidence, review items and knockout outcomes;
- any false positive or false negative is converted into a sanitized regression fixture before the pilot is closed.

A pilot is not considered successful merely because the process exits with code `0`.

## 4. Production-shaped profiling gate

The existing 20,000-fact benchmark remains a pure duplicate-consolidation regression test. BidLint 1.1 adds a second profile that deliberately includes conflicting evidence and peak-memory tracking:

```bash
python benchmarks/production_profile.py
```

The CI workload uses 6,000 canonical parameters, four evidence documents per parameter and a deterministic conflict every 25 parameters. This exercises both the equivalent-evidence and explicit-review paths while measuring consolidation CPU time and Python allocation peak memory with `tracemalloc`.

The CI ceilings are deliberately broad regression tripwires, not service-level guarantees. Customer-document extraction time depends on PDF structure, workbook complexity and optional IFC runtimes and therefore must be measured separately during a real pilot.

## 5. Pilot evidence to retain

For each completed external pilot, retain internally:

- BidLint version and commit SHA;
- sanitized fixture hash or immutable corpus identifier;
- exact CLI invocation and explicit selectors/policies;
- conformance-check result;
- benchmark/profile result from the same release line;
- human-reviewed false-positive and false-negative register;
- unresolved limitations and decision on whether each limitation blocks rollout.

The public repository should receive only sanitized regression cases and generic documentation derived from that evidence.

## 6. Adoption boundary

BidLint remains a deterministic technical compliance engine. Production adoption does not change these boundaries:

- no hidden commercial scoring;
- no automatic contractual acceptance;
- no inferred knockout criteria;
- no replacement for engineering or procurement approval;
- no claim that a synthetic benchmark is equivalent to real customer-document throughput.

The production goal is repeatable evidence, explicit uncertainty and auditable procurement hand-off.
