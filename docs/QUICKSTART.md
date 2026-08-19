# Five-minute demo

This walkthrough uses the synthetic pump documents committed under `samples/`.

## 1. Install

```bash
git clone https://github.com/yigitcan-ozturk/bidlint.git
cd bidlint
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Compare one vendor

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf
```

The terminal output classifies each requirement as `PASS`, `DEVIATION`, `MISSING` or `REVIEW` and includes an explicit reason.

## 3. Generate an auditable HTML matrix

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf --output compliance.html
```

Open `compliance.html` in a browser. The report is self-contained and includes requirement text, matched vendor fact, decision reason, confidence and source provenance.

## 4. Rank multiple vendors

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf
```

The ranking is based on deterministic technical-compliance results, not an LLM score.

Generate a shareable multi-vendor matrix:

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf \
  --output technical-tabulation.html
```

## 5. Understand unit-safe comparison

v0.2.0 converts known engineering units before evaluating a threshold.

Example:

```text
Specification: Motor power shall be minimum 10 kW.
Vendor       : Motor power: 10000 W
Decision     : PASS
Reason       : Offered 10000w (= 10kw) satisfies >= 10kw.
```

Unknown units and incompatible dimensions remain `REVIEW` instead of being guessed.

See [`ENGINEERING_UNITS.md`](ENGINEERING_UNITS.md) for the supported conversion families and deliberate limits.
