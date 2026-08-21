from __future__ import annotations

import argparse
import gc
import hashlib
import json
import statistics
import tracemalloc
from time import perf_counter

from bidlint.models import SourceRef, VendorFact
from bidlint.vendor_package import consolidate_package_facts


def make_workload(parameters: int, duplicates: int, conflict_every: int) -> list[VendorFact]:
    if parameters < 1:
        raise ValueError("parameters must be at least 1")
    if duplicates < 2:
        raise ValueError("duplicates must be at least 2")
    if conflict_every < 1:
        raise ValueError("conflict_every must be at least 1")

    facts: list[VendorFact] = []
    for index in range(parameters):
        value = float(100 + (index % 900))
        parameter = f"production parameter {index:06d}"
        conflict = index % conflict_every == 0
        for duplicate in range(duplicates):
            offered = value + 1.0 if conflict and duplicate == duplicates - 1 else value
            facts.append(
                VendorFact(
                    parameter=parameter,
                    raw_value=f"{offered:g} kW",
                    value=offered,
                    unit="kw",
                    source=SourceRef(
                        document=f"technical-evidence-{duplicate + 1:02d}.pdf",
                        page=(index % 80) + 1,
                    ),
                )
            )
    return facts


def result_digest(facts: list[VendorFact]) -> str:
    payload = "\n".join(
        "|".join(
            (
                fact.parameter,
                fact.raw_value,
                str(fact.value),
                str(fact.unit),
                fact.source.document if fact.source else "",
                fact.source.section if fact.source and fact.source.section else "",
            )
        )
        for fact in facts
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_profile(parameters: int, duplicates: int, conflict_every: int, repeats: int) -> dict[str, object]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")

    workload = make_workload(parameters, duplicates, conflict_every)
    expected_conflicts = sum(1 for index in range(parameters) if index % conflict_every == 0)
    durations: list[float] = []
    peak_mib: list[float] = []
    digests: list[str] = []
    result_count = 0
    conflict_count = 0

    for _ in range(repeats):
        gc.collect()
        tracemalloc.start()
        started = perf_counter()
        consolidated, conflicts = consolidate_package_facts("production-profile", workload)
        duration = perf_counter() - started
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        durations.append(duration)
        peak_mib.append(peak_bytes / (1024 * 1024))
        digests.append(result_digest(consolidated))
        result_count = len(consolidated)
        conflict_count = len(conflicts)

    if result_count != parameters:
        raise RuntimeError(f"unexpected consolidated fact count: {result_count} != {parameters}")
    if conflict_count != expected_conflicts:
        raise RuntimeError(f"unexpected conflict count: {conflict_count} != {expected_conflicts}")
    if len(set(digests)) != 1:
        raise RuntimeError("production profile output changed between identical runs")

    return {
        "workload": {
            "parameters": parameters,
            "duplicates_per_parameter": duplicates,
            "conflict_every": conflict_every,
            "input_facts": len(workload),
            "expected_conflicts": expected_conflicts,
            "repeats": repeats,
        },
        "result": {
            "consolidated_facts": result_count,
            "conflicts": conflict_count,
            "digest_sha256": digests[0],
        },
        "timing_seconds": {
            "runs": [round(value, 6) for value in durations],
            "median": round(statistics.median(durations), 6),
            "maximum": round(max(durations), 6),
        },
        "peak_memory_mib": {
            "runs": [round(value, 3) for value in peak_mib],
            "maximum": round(max(peak_mib), 3),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile production-shaped deterministic package consolidation with conflicts and memory tracking."
    )
    parser.add_argument("--parameters", type=int, default=6_000)
    parser.add_argument("--duplicates", type=int, default=4)
    parser.add_argument("--conflict-every", type=int, default=25)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-seconds", type=float, default=None)
    parser.add_argument("--max-peak-mib", type=float, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_profile(args.parameters, args.duplicates, args.conflict_every, args.repeats)
    print(json.dumps(payload, indent=2, sort_keys=True))

    maximum_seconds = float(payload["timing_seconds"]["maximum"])
    maximum_peak_mib = float(payload["peak_memory_mib"]["maximum"])
    failed = False
    if args.max_seconds is not None and maximum_seconds > args.max_seconds:
        print(f"profile exceeded {args.max_seconds:g}s ceiling: {maximum_seconds:g}s")
        failed = True
    if args.max_peak_mib is not None and maximum_peak_mib > args.max_peak_mib:
        print(f"profile exceeded {args.max_peak_mib:g} MiB ceiling: {maximum_peak_mib:g} MiB")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
