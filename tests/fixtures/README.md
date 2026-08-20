# Sanitized datasheet and package fixtures

These fixtures model recurring technical-datasheet and multi-document supplier-package patterns without copying any vendor document, trademarked form, confidential project data, or third-party specification text.

`sanitized_vendor_layouts.json` stores text plus approximate PDF coordinates. Tests render those definitions into temporary PDFs with ReportLab and run the normal `bidlint` parser against them.

Covered single-document patterns:

- multi-page motor datasheet with revision metadata and a parameter/unit/required/offered table
- pump performance sheet with two independent numeric fields on each visual row
- valve datasheet with an explicitly hyphenated parameter continuation and a wrapped final offered value

`sanitized_vendor_packages.json` defines five synthetic supplier packages. Tests generate temporary PDF and formula-free XLSX files, then run the normal package parser and consolidation policy.

Covered package families and behaviors:

- pump: aliased terminology plus equivalent evidence across PDF/XLSX documents
- motor: explicit compliance-schedule priority over conflicting lower-priority evidence
- valve: unresolved disagreement inside the same highest-priority document class
- HVAC: engineering-unit conversion, project aliases, copied specification exclusion and ignored commercial material
- electrical: equivalent evidence alongside an unprioritized technical conflict

Expected facts retain source provenance, and package expectations assert evidence-audit dispositions (`selected`, `equivalent-duplicate`, `conflict`, `lower-priority`) so consolidation regressions are visible in code review.
