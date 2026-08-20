# Vendor packages

`v0.7.0.dev0` introduces deterministic multi-file vendor intake with explicit document classification, project aliases and opt-in evidence priority.

A vendor package is a directory whose supported direct-child files are treated as one supplier evidence set.

```text
Supplier-A/
├── offer.xlsx
├── pump-datasheet.pdf
├── motor-datasheet.pdf
└── model.ifc
```

The existing vendor-input API accepts the directory in the same position as a single vendor document.

## Supported package files

The package adapter reads direct-child files ending in:

- `.pdf`
- `.xlsx`
- `.ifc`

Files are processed in deterministic case-insensitive filename order. Nested directories are not traversed.

All format-specific safety rules remain in force. XLSX formulas, macros, external relationships, hidden evidence sheets, merged cells and ambiguous layouts are still rejected. IFC evidence still requires explicit element scope through the existing IFC selection rules.

## Document classification

Every direct-child file receives one visible `DocumentClass`:

- `specification`
- `datasheet`
- `compliance-schedule`
- `technical-offer`
- `ignored`

Classification is deterministic and filename-based. Explicit markers such as `datasheet`, `compliance`, `specification`, `offer`, `proposal`, `commercial` and `pricing` are recognized first. Supported files without a stronger marker retain backwards-compatible format fallbacks: XLSX defaults to `compliance-schedule`; PDF and IFC default to `technical-offer`.

Unsupported file types are always `ignored`.

Documents classified as `specification` or `ignored` never become vendor evidence. This prevents a copied employer specification or commercial pricing document from silently satisfying a technical requirement.

Programmatic users can override a supported package file by exact filename:

```python
from bidlint.vendor_package import parse_vendor_package

package = parse_vendor_package(
    "Supplier-A",
    document_classes={
        "vendor-submission.pdf": "technical-offer",
        "pricing.pdf": "ignored",
    },
)
```

Unknown filenames, unknown classes and attempts to treat unsupported file types as technical evidence are rejected instead of guessed.

The resolved mapping is available through `VendorPackage.document_classes`. Explicitly ignored files remain visible through `VendorPackage.ignored_documents`.

## Project terminology aliases

Project-specific terminology aliases participate in package consolidation before the normal compliance comparison.

For example:

```json
{
  "supplier rated output": "motor power"
}
```

With:

```bash
bidlint compare specification.pdf Supplier-A/ --aliases aliases.json
```

the same normalized alias mapping is used twice:

1. package evidence is grouped by the aliased canonical parameter before duplicate/conflict consolidation;
2. the consolidated vendor facts are matched against specification requirements by the existing comparator.

This means `supplier rated output = 11 kW` in one package document and `motor power = 11000 W` in another become equivalent evidence rather than two unrelated facts. If the aliased facts disagree, the existing conflict rules still apply and produce `REVIEW` unless an explicit evidence-priority policy resolves the class-level conflict.

Aliases do not introduce fuzzy grouping, hidden precedence or additional confidence.

## Duplicate evidence

Facts are grouped by the existing conservative terminology canonicalization.

Equivalent duplicates collapse deterministically. Numeric facts are considered equivalent only when they are equal directly or through an existing deterministic engineering-unit conversion.

For example, these two facts are equivalent:

```text
motor.pdf   motor power       11 kW
offer.xlsx  rated motor power 11000 W
```

No extra confidence is inferred merely because the value appears twice.

## Conflicting evidence without priority

BidLint does not silently choose one document when a package contains different evidence for the same canonical parameter.

For example:

```text
motor.pdf   motor power       11 kW
offer.xlsx  rated motor power 15 kW
```

With no priority policy, the package adapter replaces that parameter group with one provenance-preserving conflict fact. The normal evaluator recognizes that fact and emits `REVIEW`.

A reason is deterministic and includes the contributing evidence locations, for example:

```text
Conflicting vendor evidence for motor power: motor.pdf:page 2 = 11 kW; offer.xlsx:line 7 = 15 kW. Review required.
```

This remains the default. File format never creates hidden source precedence.

## Explicit evidence priority

A caller may opt in to an ordered priority of technical document classes:

```python
package = parse_vendor_package(
    "Supplier-A",
    evidence_priority=(
        "compliance-schedule",
        "technical-offer",
        "datasheet",
    ),
)
```

The first listed class has the highest priority. Unlisted technical classes are lower than any explicitly listed class.

Priority only narrows a conflicting parameter group to the highest available listed class. If the surviving highest-priority evidence is equivalent, BidLint selects its first deterministic occurrence. If two highest-priority documents still disagree, the result remains `REVIEW`; priority never breaks a tie within the same class.

For example, a compliance schedule can explicitly override a conflicting datasheet when the policy ranks `compliance-schedule` above `datasheet`. Two disagreeing compliance schedules still force review.

Only `datasheet`, `compliance-schedule` and `technical-offer` may appear in an evidence-priority policy. Duplicate or invalid classes are rejected.

The normalized policy is available through `VendorPackage.evidence_priority`.

## Current scope

Current deliberate limits include:

- only direct-child documents are considered
- document classification uses deterministic filename rules plus exact programmatic overrides; package manifest and CLI override surfaces are not added yet
- mixed package ranking that requires global IFC/XLSX selectors is still being hardened
- package-level audit output beyond the existing finding provenance is still planned

See [`ROADMAP.md`](../ROADMAP.md) for the remaining v0.7 work.
