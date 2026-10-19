"""Independent synthetic contract probes against the real BidLint comparison engine.

These cases do not establish real-world accuracy or validate PDF/XLSX extraction.
"""
from __future__ import annotations

import json

import pytest

from bidlint.compare import compare
from bidlint.models import Requirement, SourceRef, Status, VendorFact


@pytest.mark.parametrize(
    ("operator", "required", "offered", "expected"),
    [
        (">=", 10.0, 10.0, Status.PASS),
        (">=", 10.0, 12.0, Status.PASS),
        (">=", 10.0, 9.0, Status.DEVIATION),
        ("<=", 10.0, 11.0, Status.DEVIATION),
        ("=", 10.0, 10.0, Status.PASS),
    ],
)
def test_numeric_engine_decisions(operator, required, offered, expected):
    req = Requirement(id="V13-001", text="Motor power", parameter="motor power",
                      operator=operator, value=required, unit="kw",
                      source=SourceRef(document="synthetic-spec.pdf", page=1))
    fact = VendorFact(parameter="motor power", raw_value=f"{offered} kW",
                      value=offered, unit="kw",
                      source=SourceRef(document="synthetic-vendor.pdf", page=2))
    report = compare([req], [fact], "synthetic-spec.pdf", "synthetic-vendor.pdf")
    assert report.findings[0].status == expected
    assert report.findings[0].vendor_fact.source.page == 2


def test_missing_evidence_does_not_pass():
    req = Requirement(id="V13-002", text="Motor power", parameter="motor power",
                      operator=">=", value=10, unit="kw")
    report = compare([req], [], "synthetic-spec.pdf", "synthetic-vendor.pdf")
    assert report.findings[0].status == Status.MISSING
    assert report.findings[0].vendor_fact is None


def test_nonnumeric_evidence_requires_review():
    req = Requirement(id="V13-003", text="Motor power", parameter="motor power",
                      operator=">=", value=10, unit="kw")
    fact = VendorFact(parameter="motor power", raw_value="as required")
    report = compare([req], [fact], "synthetic-spec.pdf", "synthetic-vendor.pdf")
    assert report.findings[0].status == Status.REVIEW


def test_same_inputs_produce_same_serialized_report():
    req = Requirement(id="V13-004", text="Motor power", parameter="motor power",
                      operator=">=", value=10, unit="kw")
    fact = VendorFact(parameter="motor power", raw_value="12 kW", value=12, unit="kw")
    outputs = [
        json.dumps(compare([req], [fact], "spec.pdf", "vendor.pdf").to_dict(),
                   sort_keys=True, separators=(",", ":"))
        for _ in range(3)
    ]
    assert len(set(outputs)) == 1
