# BidLint 30-Second Demo Script

This script is designed for a short LinkedIn product demo using only repository sample data.

## Objective

Show the product in one flow:

**Specification + vendor evidence -> BidLint -> PASS / DEVIATION / MISSING / REVIEW -> reviewable output**

## Recording sequence

### 0-4 seconds — Problem

On screen:

```text
Still comparing technical bids manually?
```

Show the sample specification and vendor documents briefly.

### 4-9 seconds — Run

Terminal:

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf
```

Overlay:

```text
Specification + vendor evidence
```

### 9-18 seconds — Findings

Pause on the result and visually emphasize:

```text
PASS
DEVIATION
MISSING
REVIEW
```

Overlay:

```text
Explicit outcomes. Source-backed evidence.
```

### 18-24 seconds — Multi-vendor workflow

Terminal:

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf \
  --output technical-tabulation.xlsx
```

Show the generated reviewable technical tabulation briefly.

### 24-30 seconds — Close

On screen:

```text
BidLint
Open-source technical bid compliance engine
Evidence before confidence

github.com/yigitcan-ozturk/bidlint
```

## Recording principles

- Use repository sample data only.
- Keep the terminal font large enough for mobile viewing.
- Do not scroll through long output.
- Do not make unsupported time-saving claims.
- Keep `REVIEW` visible: the product supports engineering judgment rather than pretending to replace it.
- Target total duration: 25-30 seconds.
