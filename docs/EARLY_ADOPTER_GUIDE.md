# BidLint Early Adopter Guide

This guide is for engineers, procurement professionals, proposal engineers and technical buyers who want to test BidLint on a realistic technical-bid workflow.

## Goal

The goal is not to prove that BidLint works on easy examples. We want to find the cases where a real engineering team would hesitate to trust or adopt it.

Please use only sanitized, non-confidential or recreated documents.

## 10-minute test

### 1. Install the stable release

```bash
python -m pip install "bidlint @ git+https://github.com/yigitcan-ozturk/bidlint.git@v1.1.0"
```

Verify the CLI:

```bash
bidlint --help
```

### 2. Try the included sample workflow

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf
```

For a multi-vendor comparison:

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf \
  --output technical-tabulation.xlsx
```

### 3. Try a sanitized real workflow

Good inputs include:

- technical specifications
- vendor datasheets
- technical quotations
- submittals
- explicit XLSX technical offer tables
- explicitly scoped IFC properties

Do not upload confidential customer, supplier or project data to public GitHub issues.

### 4. Review the four outcomes

- `PASS` — evidence deterministically satisfies the requirement
- `DEVIATION` — evidence deterministically conflicts with the requirement
- `MISSING` — sufficient matching evidence was not found
- `REVIEW` — evidence exists, but the decision is ambiguous or unsafe to automate

## What feedback is most useful?

We especially want examples of:

- false positives or false negatives
- terminology mismatches
- unit conversion edge cases
- ambiguous or qualitative requirements
- conflicting evidence across vendor documents
- PDF/XLSX workflow friction
- missing procurement hand-off fields
- cases that should have produced `REVIEW`
- anything that would block adoption in a real team

## What to include in feedback

When possible, include:

1. Industry / workflow
2. Input types used
3. Command executed
4. Expected behavior
5. Actual behavior
6. Why the result matters in a real technical evaluation
7. Sanitized evidence or a minimal recreated example

## Confidentiality

Never post confidential specifications, bids, quotations, customer information, supplier pricing or proprietary drawings in a public issue.

If an issue can only be explained with sensitive data, recreate the smallest non-confidential example that demonstrates the behavior.

## Where to respond

- Early adopter coordination: https://github.com/yigitcan-ozturk/bidlint/issues/61
- Bugs and reproducible failures: open a GitHub issue
- Contributions: pull requests are welcome when they preserve deterministic behavior, provenance and explicit uncertainty

## Product principle

**Evidence before confidence.**

BidLint should not replace engineering judgment. It should make requirements, vendor evidence, deviations and uncertainty easier to inspect, reproduce and review.
