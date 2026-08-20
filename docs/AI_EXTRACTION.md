# Optional structured extraction

`bidlint` v0.3 introduces a provider-neutral boundary for optional AI-assisted or external structured extraction.

The core rule does not change: **providers may propose structured evidence; they do not decide technical compliance.** Accepted candidates are converted into the existing `Requirement` and `VendorFact` models and then evaluated by the same deterministic matching, unit-conversion and status rules used by the built-in parser.

## No bundled AI dependency

The base package does not depend on an LLM SDK, model provider, API key or network service. Existing commands and deterministic PDF parsing continue to work without configuring any extractor.

An integration implements the `StructuredExtractor` protocol:

```python
from pathlib import Path

from bidlint.extraction import ExtractionBatch, ExtractionKind


class MyExtractor:
    name = "my-provider"

    def extract(self, document: Path, kind: ExtractionKind) -> ExtractionBatch:
        ...
```

The provider returns an `ExtractionBatch` containing `RequirementCandidate` or `VendorFactCandidate` objects.

## Required evidence contract

Every candidate must include:

- provider confidence from `0.0` to `1.0`
- a positive source page number
- a non-empty evidence snippet copied from that page
- structured fields appropriate to the extraction kind

The default minimum confidence is `0.75`.

`bidlint` re-reads the source PDF and normalizes whitespace before checking that the evidence snippet actually occurs on the declared page. A candidate is rejected if the page is outside the document or if the evidence cannot be found there.

This is intentionally stricter than trusting provider-supplied page metadata.

## Requirement candidate

```python
from bidlint.extraction import Evidence, RequirementCandidate

candidate = RequirementCandidate(
    text="Motor power shall be minimum 10 kW",
    parameter="motor power",
    operator=">=",
    value=10,
    unit="kW",
    mandatory=True,
    confidence=0.97,
    evidence=Evidence(
        page=4,
        text="Motor power shall be minimum 10 kW",
    ),
)
```

Numeric requirements must provide the comparison operator and numeric value together. Supported operators remain `>=`, `<=` and `=`. Qualitative requirements may leave both fields empty.

## Vendor fact candidate

```python
from bidlint.extraction import Evidence, VendorFactCandidate

candidate = VendorFactCandidate(
    parameter="motor power",
    raw_value="11000 W",
    value=11000,
    unit="W",
    confidence=0.95,
    evidence=Evidence(
        page=2,
        text="Motor power: 11000 W",
    ),
)
```

Provider confidence is extraction confidence only. It is not reused as the final compliance confidence. Once accepted, the normal deterministic parameter matcher calculates its own matching confidence.

## Validation

Use `validate_extraction()` when an integration already has an `ExtractionBatch`:

```python
validated = validate_extraction(
    "vendor.pdf",
    batch,
    min_confidence=0.80,
)

print(validated.items)
print(validated.rejected)
```

Use `extract_with_provider()` to invoke a provider and validate the returned batch in one step:

```python
validated = extract_with_provider(
    "vendor.pdf",
    ExtractionKind.VENDOR,
    extractor,
)
```

Provider identity and requested extraction kind are checked before conversion.

## Rejection behavior

Invalid candidates are not silently coerced. They are returned in `ValidatedExtraction.rejected` with an index and reason, including cases such as:

- confidence below threshold
- confidence outside `[0, 1]` or non-finite
- invalid or out-of-range page number
- evidence snippet absent from the declared page
- candidate type inconsistent with the requested extraction kind
- unsupported requirement operator
- numeric requirement missing either operator or value
- non-finite numeric values

Rejected candidates never enter `compare()`.

## Deterministic evaluation remains authoritative

After validation, provider-assisted extraction uses the existing core:

```python
report = compare(
    validated_requirements.items,
    validated_vendor_facts.items,
    "specification.pdf",
    "vendor.pdf",
)
```

The provider cannot directly emit `PASS`, `DEVIATION`, `MISSING` or `REVIEW`. Those statuses remain outputs of the deterministic evaluation layer.

## Deliberate limits

- no provider implementation is bundled in the core package
- no automatic network calls are made
- evidence validation confirms page-local text presence; it does not prove semantic correctness
- a high provider confidence does not override deterministic uncertainty
- provider output cannot introduce new comparison operators or unit-conversion rules
- OCR and image interpretation remain separate concerns

The design goal is to make optional AI extraction replaceable and auditable without turning model output into the compliance authority.
