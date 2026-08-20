# Vendor packages

`v0.7.0.dev0` introduces a conservative first slice of multi-file vendor intake.

A vendor package is a directory whose supported direct-child files are treated as one supplier evidence set.

```text
Supplier-A/
├── offer.xlsx
├── pump-datasheet.pdf
├── motor-datasheet.pdf
└── model.ifc
```

The existing CLI vendor argument can point at the directory:

```bash
bidlint compare specification.pdf Supplier-A/
```

Selector-free package inputs can also participate in normal ranking:

```bash
bidlint rank specification.pdf Supplier-A/ Supplier-B/
```

## Supported package files

The initial package adapter reads direct-child files ending in:

- `.pdf`
- `.xlsx`
- `.ifc`

Files are processed in a deterministic case-insensitive filename order. Nested directories are not traversed. Other direct-child files are excluded from technical evidence and remain visible through the `VendorPackage.ignored_documents` library field.

All format-specific safety rules remain in force. XLSX formulas, macros, external relationships, hidden evidence sheets, merged cells and ambiguous layouts are still rejected. IFC evidence still requires explicit element scope through the existing IFC selection rules.

## Duplicate evidence

Facts are grouped by the existing conservative terminology canonicalization.

Equivalent duplicates collapse to the first deterministic evidence occurrence. Numeric facts are considered equivalent only when they are equal directly or through an existing deterministic engineering-unit conversion.

For example, these two facts are equivalent:

```text
motor.pdf   motor power       11 kW
offer.xlsx  rated motor power 11000 W
```

No extra confidence is inferred merely because the value appears twice.

## Conflicting evidence

BidLint does not silently choose one document when a package contains different evidence for the same canonical parameter.

For example:

```text
motor.pdf   motor power       11 kW
offer.xlsx  rated motor power 15 kW
```

The package adapter replaces that parameter group with one provenance-preserving conflict fact. The normal evaluator recognizes that fact and emits `REVIEW`.

A reason is deterministic and includes the contributing evidence locations, for example:

```text
Conflicting vendor evidence for motor power: motor.pdf:page 2 = 11 kW; offer.xlsx:line 7 = 15 kW. Review required.
```

This preserves the core rule: source disagreement cannot become an automatic technical decision.

## Current scope

This is the first v0.7 intake slice, not the complete vendor-package contract.

Current deliberate limits include:

- only direct-child documents are considered
- unsupported document types are not classified yet
- package conflict consolidation uses the built-in terminology registry through normal CLI dispatch; explicit CLI alias threading is still planned
- mixed package ranking that requires global IFC/XLSX selectors is still being hardened
- source-priority policy is not inferred automatically
- no document is declared authoritative merely because it is PDF, XLSX or IFC
- package-level audit output beyond the existing finding provenance is still planned

See [`ROADMAP.md`](../ROADMAP.md) for the remaining v0.7 work.
