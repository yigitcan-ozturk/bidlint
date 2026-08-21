# Pilot sanitization scan

BidLint 1.1 includes a conservative pre-flight scanner for external pilot corpora.

Run it before producing pilot evidence:

```bash
bidlint-pilot-scan pilot.json --json --output sanitization-scan.json
```

The installed `bidlint-pilot` command is guarded by the same scanner. If a blocker is detected, pilot execution stops before compliance evidence is generated.

## What is blocked automatically

The scanner checks declared specification, vendor, alias and knockout-policy content for common leakage signals without copying the matched text into its output. Blockers include:

- email addresses and international phone-like contact data;
- currency amounts and common commercial/Incoterm/payment terminology;
- legal-entity-like names and tax-identifier labels;
- non-generic PDF author/title/subject metadata;
- PDF embedded attachments;
- OOXML comments and core metadata;
- hidden or veryHidden XLSX worksheets;
- XLSX external links;
- symlinked corpus content.

A blocker produces process exit code `3`. I/O failures use `5`; invalid CLI usage uses argparse's `2`.

## Manual-review findings

Some risks cannot be safely resolved with deterministic text inspection. These are emitted as `REVIEW` findings rather than silently treated as clean:

- PDF visual content, drawings, stamps, screenshots and raster images;
- OOXML embedded media;
- standalone image files;
- unsupported binary formats;
- URLs that may be intentionally public references but still need a human check;
- identity/address/signature labels requiring contextual inspection.

The scanner does **not** OCR visual material. A result with `automated_clear: true` can therefore still have `manual_review_required: true`.

## Non-leaking output

Finding records contain only category, logical file name, location, count and remediation message. The matched email, phone number, company name, price or metadata value is intentionally omitted so the scan report does not become a second copy of sensitive data.

## Pilot gate behavior

`bidlint-pilot` now performs this sequence:

1. parse and validate the strict pilot manifest;
2. run the sanitization scan;
3. stop when any `BLOCK` finding exists;
4. otherwise execute the normal compare/rank path repeatedly;
5. validate output conformance and deterministic digests;
6. produce pilot evidence.

Manual review remains mandatory under `docs/PRODUCTION_ADOPTION.md`. The automated scan is a leakage tripwire, not a confidentiality certification.

## External pilot rule

A real external pilot should retain the scan JSON alongside pilot evidence and reviewer notes. Raw external/customer documents must not be committed to the public repository. Only sanitized regression fixtures and non-sensitive evidence derived from the pilot may be published.
