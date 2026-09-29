# Contributing

`bidlint` is intentionally small and auditable. Contributions should preserve deterministic behavior and source traceability.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check src tests
```

## Principles

1. A finding must be traceable to source pages.
2. Deterministic rules must remain understandable without an LLM.
3. AI-assisted extraction, when added, must be optional and never silently override deterministic policy.
4. New matching logic needs tests showing both correct matches and false-positive resistance.

## External pilot / validation

We welcome engineering, EPC, industrial procurement and technical-bid practitioners who can test BidLint on a real or sanitized specification/vendor package.

A useful pilot does not require sharing confidential commercial material. Sanitized or synthetic documents that preserve the technical structure are welcome. Useful feedback includes incorrect PASS/DEVIATION decisions, evidence that should remain REVIEW, missing extraction scope, unit/terminology edge cases, and workbook outputs that do not match a real evaluation workflow.

Please open a public issue with the document types, engineering domain, expected result and observed result. Do not upload confidential, personal or commercially restricted documents to a public issue.
