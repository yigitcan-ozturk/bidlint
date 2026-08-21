from __future__ import annotations

from dataclasses import fields

from .errors import ExitCode
from .models import Finding, Requirement, SourceRef, VendorFact

STABLE_CONTRACT_VERSION = "1"

STATUS_VALUES = ("PASS", "DEVIATION", "MISSING", "REVIEW")
KNOCKOUT_STATUS_VALUES = ("ELIGIBLE", "REVIEW_REQUIRED", "DISQUALIFIED")

CLI_REQUIRED_COMMANDS = ("compare", "rank", "extract")
CLI_EXIT_CODES = {
    "SUCCESS": 0,
    "USAGE": 2,
    "INPUT": 3,
    "CONFIG": 4,
    "IO": 5,
    "INTERNAL": 70,
}

SOURCE_REF_REQUIRED_FIELDS = ("document", "page", "line", "section")
REQUIREMENT_REQUIRED_FIELDS = (
    "id",
    "text",
    "parameter",
    "operator",
    "value",
    "unit",
    "mandatory",
    "source",
)
VENDOR_FACT_REQUIRED_FIELDS = ("parameter", "raw_value", "value", "unit", "source")
FINDING_REQUIRED_FIELDS = ("requirement", "vendor_fact", "status", "confidence", "reason")
REPORT_REQUIRED_KEYS = (
    "tool",
    "version",
    "specification",
    "vendor",
    "compliance_score",
    "counts",
    "findings",
)
REPORT_OPTIONAL_KEYS = ("knockout",)


def _field_names(model: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(model))


def stable_contract_manifest() -> dict[str, object]:
    """Return the machine-readable compatibility floor for BidLint 1.x.

    Required fields/commands may gain additive companions in a backward-compatible
    minor release, but the entries in this manifest cannot be removed, renamed, or
    semantically repurposed before the next major version.
    """

    return {
        "contract_version": STABLE_CONTRACT_VERSION,
        "statuses": list(STATUS_VALUES),
        "knockout_statuses": list(KNOCKOUT_STATUS_VALUES),
        "cli": {
            "required_commands": list(CLI_REQUIRED_COMMANDS),
            "exit_codes": dict(CLI_EXIT_CODES),
        },
        "models": {
            "SourceRef": list(SOURCE_REF_REQUIRED_FIELDS),
            "Requirement": list(REQUIREMENT_REQUIRED_FIELDS),
            "VendorFact": list(VENDOR_FACT_REQUIRED_FIELDS),
            "Finding": list(FINDING_REQUIRED_FIELDS),
        },
        "report_json": {
            "required_keys": list(REPORT_REQUIRED_KEYS),
            "optional_keys": list(REPORT_OPTIONAL_KEYS),
        },
        "scoring": {
            "evaluable_statuses": ["PASS", "DEVIATION", "MISSING"],
            "review_in_denominator": False,
            "empty_score": 0.0,
            "precision_decimals": 1,
        },
    }


def validate_runtime_contract() -> None:
    """Fail fast if the runtime no longer satisfies the published 1.x floor."""

    models = {
        SourceRef: SOURCE_REF_REQUIRED_FIELDS,
        Requirement: REQUIREMENT_REQUIRED_FIELDS,
        VendorFact: VENDOR_FACT_REQUIRED_FIELDS,
        Finding: FINDING_REQUIRED_FIELDS,
    }
    for model, required in models.items():
        actual = set(_field_names(model))
        missing = set(required).difference(actual)
        if missing:
            raise RuntimeError(f"{model.__name__} compatibility fields missing: {sorted(missing)}")

    actual_exit_codes = {member.name: int(member) for member in ExitCode}
    if actual_exit_codes != CLI_EXIT_CODES:
        raise RuntimeError("public CLI exit-code contract changed")
