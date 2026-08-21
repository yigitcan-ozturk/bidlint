from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from time import perf_counter

from bidlint.models import SourceRef, VendorFact
from bidlint.vendor_package import consolidate_package_facts


def make_workload(parameters: int, duplicates: int) -> list[VendorFact]:
    if parameters < 1:
        raise ValueError("parameters must be at least 1")
    if duplicates < 1:
        raise ValueError("duplicates must be at least 1")

    facts: list[VendorFact] = []
    for index in range(parameters):
        value = float(100 + (index % 900))
        parameter = f"benchmark parameter {index:06d}"
        for duplicate in range(duplicates):
            facts.append(
                VendorFact(
                    parameter=parameter,
                    raw_value=f"{value:g} kW",
                    value=value,
                    unit="kw",
                    source=SourceRef(
                        document=f"datasheet-{duplicate + 1:02d}.pdf",
                        page=(index % 50) + 1,
                    ),
                )
            )
    return facts


def result_digest(facts: list[VendorFact]) -> str:
    payload = "\n".join(
        f"{fact.parameter}|{fact.raw_value}|{fact.value}|{fact.unit}"
        for fact in facts
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_benchmark(parameters: int, duplicates: int, repeats: int) -> dict[str, object]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")

    workload = make_workload(parameters, duplicates)
    durations: list[float] = []
    digests: list[str] = []
    result_count = 0
    conflict_count = 0

    for _ in range(repeats):
        started = perf_counter()
        consolidated, conflicts = consolidate_package_facts("benchmark-package", workload)
        durations.append(perf_counter() - started)
        digests.append(result_digest(consolidated))
        result_count = len(consolidated)
        conflict_count = len(conflicts)

    if result_count != parameters:
        raise RuntimeError(f"unexpected consolidated fact count: {result_count} != {parameters}")
    if conflict_count != 0:
        raise RuntimeError(f"unexpected benchmark conflicts: {conflict_count}")
    if len(set(digests)) != 1:
        raise RuntimeError("benchmark output changed between identical runs")

    return {
        "workload": {
            "parameters": parameters,
            "duplicates_per_parameter": duplicates,
            "input_facts": len(workload),
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
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark deterministic large-package evidence consolidation.")
    parser.add_argument("--parameters", type=int, default=5_000)
    parser.add_argument("--duplicates", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="optional maximum allowed duration for any measured consolidation run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_benchmark(args.parameters, args.duplicates, args.repeats)
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.max_seconds is not None:
        maximum = float(payload["timing_seconds"]["maximum"])
        if maximum > args.max_seconds:
            print(f"benchmark exceeded {args.max_seconds:g}s ceiling: {maximum:g}s")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
