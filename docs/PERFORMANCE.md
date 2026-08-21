# Large-package performance benchmark

BidLint v0.9 includes a deterministic benchmark for the package-evidence consolidation boundary.

The benchmark generates a fixed synthetic workload rather than using customer documents. Each parameter appears in multiple source documents with equivalent numeric evidence, exercising canonical parameter grouping, duplicate comparison, provenance handling and deterministic selection without introducing network or filesystem variability.

## CI workload

The pull-request benchmark runs on Python 3.13 with:

- 5,000 unique parameters;
- 4 equivalent source facts per parameter;
- 20,000 input `VendorFact` records total;
- 3 identical consolidation runs;
- a 15-second maximum ceiling for any single run.

The timing ceiling is intentionally broad. It is a regression tripwire, not a claim about production throughput or a hardware-independent service-level objective.

## Determinism check

Every run must produce:

- exactly 5,000 consolidated facts;
- zero conflicts for the equivalent-evidence workload;
- the same SHA-256 digest of the consolidated output across all repeated runs.

A timing result is therefore accepted only when the functional output is also stable.

## Local execution

```bash
python benchmarks/large_package.py
```

A larger workload can be exercised explicitly:

```bash
python benchmarks/large_package.py --parameters 10000 --duplicates 5 --repeats 5
```

To apply a local regression ceiling:

```bash
python benchmarks/large_package.py --max-seconds 15
```

This benchmark isolates consolidation cost. PDF extraction, OOXML parsing and IfcOpenShell parsing have separate correctness/regression coverage and depend more heavily on document structure and optional runtimes, so they are not mixed into this deterministic package benchmark.
