from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    DEVIATION = "DEVIATION"
    MISSING = "MISSING"
    REVIEW = "REVIEW"


@dataclass(slots=True)
class SourceRef:
    document: str
    page: int | None = None
    line: int | None = None
    section: str | None = None


@dataclass(slots=True)
class Requirement:
    id: str
    text: str
    parameter: str
    operator: str | None = None
    value: float | None = None
    unit: str | None = None
    mandatory: bool = True
    source: SourceRef | None = None


@dataclass(slots=True)
class VendorFact:
    parameter: str
    raw_value: str
    value: float | None = None
    unit: str | None = None
    source: SourceRef | None = None


@dataclass(slots=True)
class Finding:
    requirement: Requirement
    vendor_fact: VendorFact | None
    status: Status
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class ComplianceReport:
    specification: str
    vendor: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {status.value: sum(f.status == status for f in self.findings) for status in Status}

    @property
    def compliance_score(self) -> float:
        evaluable = [f for f in self.findings if f.status in {Status.PASS, Status.DEVIATION, Status.MISSING}]
        if not evaluable:
            return 0.0
        passed = sum(f.status == Status.PASS for f in evaluable)
        return round(100.0 * passed / len(evaluable), 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": "bidlint",
            "version": "0.1.0",
            "specification": self.specification,
            "vendor": self.vendor,
            "compliance_score": self.compliance_score,
            "counts": self.counts,
            "findings": [f.to_dict() for f in self.findings],
        }
