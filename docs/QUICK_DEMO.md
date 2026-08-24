# BidLint — 60-second zero-install walkthrough

You do **not** need to install BidLint to understand the core workflow.

This walkthrough uses only synthetic repository sample data. It contains no confidential or third-party project information.

## The engineering question

A pump specification contains five requirements. Vendor A submits technical evidence against them.

| Requirement | Specification | Vendor A evidence | BidLint outcome |
| --- | --- | --- | --- |
| Motor efficiency | minimum 90% | 93% | `PASS` |
| Noise level | maximum 70 dB | 68 dB | `PASS` |
| IP rating | minimum 65 | 54 | `DEVIATION` |
| Housing | corrosion resistant | 316L stainless steel | `REVIEW` |
| Flow rate | minimum 120 m3/h | not found | `MISSING` |

Result for Vendor A:

```text
PASS       2
DEVIATION  1
MISSING    1
REVIEW     1
```

The important part is not the score. It is the evidence trail:

- `PASS` only when offered evidence deterministically satisfies the requirement.
- `DEVIATION` only when offered evidence deterministically conflicts with it.
- `MISSING` when sufficiently similar evidence cannot be found.
- `REVIEW` when evidence exists but the decision is qualitative, ambiguous or unsafe to automate.

## Example finding

Specification:

```text
IP rating shall be minimum 65
Source: pump-specification.pdf, page 1, section 6.4
```

Vendor evidence:

```text
Ingress protection: 54
Source: vendor-a-submittal.pdf, page 1
```

BidLint:

```text
DEVIATION
Offered 54 does not satisfy >= 65.
```

## Multi-vendor comparison

The included Vendor B sample produces:

```text
Vendor B  100.0  4 PASS / 0 DEVIATION / 0 MISSING / 1 REVIEW
Vendor A   50.0  2 PASS / 1 DEVIATION / 1 MISSING / 1 REVIEW
```

`REVIEW` remains visible instead of being hidden by the ranking.

## Run it yourself

Install the stable release directly from GitHub:

```bash
python -m pip install "bidlint @ git+https://github.com/yigitcan-ozturk/bidlint.git@v1.1.0"
```

Compare one vendor:

```bash
bidlint compare samples/pump-specification.pdf samples/vendor-a-submittal.pdf
```

Rank two vendors and export a reviewable workbook:

```bash
bidlint rank samples/pump-specification.pdf \
  samples/vendor-a-submittal.pdf \
  samples/vendor-b-submittal.pdf \
  --output technical-tabulation.xlsx
```

## Source files

- [`samples/pump-specification.pdf`](../samples/pump-specification.pdf)
- [`samples/vendor-a-submittal.pdf`](../samples/vendor-a-submittal.pdf)
- [`samples/vendor-b-submittal.pdf`](../samples/vendor-b-submittal.pdf)
- [`samples/demo-report.json`](../samples/demo-report.json)
- [`samples/demo-report.html`](../samples/demo-report.html)
- [`samples/portfolio.json`](../samples/portfolio.json)

## Early-adopter feedback

We are looking for engineers, procurement professionals, proposal engineers and technical buyers who regularly compare specifications against vendor offers, datasheets or submittals.

Use sanitized / non-confidential workflows only.

- [Early adopter guide](EARLY_ADOPTER_GUIDE.md)
- [Early adopter coordination — Issue #61](https://github.com/yigitcan-ozturk/bidlint/issues/61)

**Evidence before confidence.**