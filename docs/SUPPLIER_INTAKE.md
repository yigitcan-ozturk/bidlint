# Supplier Intake MVP

BidLint's deterministic evaluator remains buyer-side and unchanged. The Supplier Intake MVP adds a zero-server clarification hand-off for suppliers who should not need Python, GitHub or a BidLint installation.

## Workflow

1. Run the normal comparison and export the stable clarification register:

```bash
bidlint compare specification.pdf vendor-offer.pdf \
  --clarifications-output clarifications.json
```

2. Convert the clarification register into a self-contained supplier form:

```bash
bidlint-supplier-intake clarifications.json supplier-clarification.html
```

3. Send `supplier-clarification.html` to the supplier through the normal approved project channel.

4. The supplier opens the file in a browser, completes only the `REVIEW` / `MISSING` clarification items and clicks **Download response JSON**.

5. The supplier returns `bidlint-supplier-response.json` through the normal approved project channel.

## Privacy boundary

The generated HTML is offline by design:

- no server is required;
- no network request is made by the form;
- no confidential offer or response is uploaded to GitHub or a third-party service;
- the supplier remains in control of the response file and return channel.

This MVP intentionally does **not** provide authentication, hosted storage, email delivery, contractual acceptance or automatic status changes. A supplier response is evidence for a new buyer-side review; it does not automatically convert a BidLint finding to `PASS`.

## Response contract

The downloaded response uses the additive contract:

```text
bidlint.supplier-clarification-response / version 1
```

Each response keeps the original requirement id, parameter, finding status and clarification category, then adds:

- supplier response;
- offered / confirmed value;
- unit or designation;
- evidence reference;
- optional supplier comment;
- responder name and company.

## Next validation

Use a sanitized real supplier clarification workflow to validate:

- whether the questions are understandable without buyer assistance;
- whether evidence references are sufficient for technical re-review;
- whether the response JSON should feed a future deterministic re-evaluation boundary;
- which controls are required before a hosted supplier portal is considered.

**Evidence before confidence.**
