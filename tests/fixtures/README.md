# Sanitized datasheet fixtures

These fixtures model recurring technical-datasheet layout patterns without copying any vendor document, trademarked form, confidential project data, or third-party specification text.

The JSON stores text plus approximate PDF coordinates. Tests render those definitions into temporary PDFs with ReportLab and run the normal `bidlint` parser against them.

Covered patterns:

- multi-page motor datasheet with revision metadata and a parameter/unit/required/offered table
- pump performance sheet with two independent numeric fields on each visual row
- valve datasheet with an explicitly hyphenated parameter continuation and a wrapped final offered value

Expected facts include source-page provenance so layout extraction regressions are visible in code review.
