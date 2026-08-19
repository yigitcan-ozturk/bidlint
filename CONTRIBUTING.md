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
