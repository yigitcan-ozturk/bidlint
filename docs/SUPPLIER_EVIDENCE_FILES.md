# Supplier Evidence File Manifest

BidLint v1.2 keeps supplier collaboration offline-first. Supplier responses may arrive with certificates, calculations, test reports, drawings or other supporting files. Those bytes must be traceable without uploading them into BidLint or changing evaluator semantics.

`bidlint-supplier-files` creates a deterministic manifest bound to an existing buyer-side supplier clarification review.

The input evidence map is a local JSON object:

```json
{
  "files": [
    {
      "path": "MTC-317L.pdf",
      "requirement_ids": ["R0001"],
      "evidence_types": ["certificate"],
      "note": "Mill test certificate returned with supplier clarification"
    }
  ]
}
```

Run:

```text
bidlint-supplier-files buyer-review.json evidence-map.json evidence-files.json
```

Or create it as part of the external pilot work package:

```text
bidlint-supplier-pilot prepare-return register.json supplier-response.json pilot-return \
  --evidence-map evidence-map.json
```

That produces `evidence-files.json` alongside `buyer-review.json`, `evidence-assessment.json` and `pilot-return-manifest.json`, with the evidence manifest digest recorded in the pilot-return manifest.

The output contract is `bidlint.supplier-evidence-files / 1` and records, for every file:

- deterministic file ID (`F001`, `F002`, ...);
- stable reference token (`file:F001`);
- basename only (local directory paths are not persisted);
- exact byte SHA-256;
- exact byte length;
- guessed media type when available;
- requirement IDs checked against the bound buyer review;
- evidence types checked against `calculation`, `certificate`, `test_basis`, `supporting_document`;
- operator note.

The manifest is bound to the canonical SHA-256 of the exact buyer review and the byte SHA-256 of the evidence-map input. Duplicate source paths, duplicate basenames, unknown requirement IDs, unsupported evidence types, missing files and directories fail closed.

## Evidence assessment binding

A human evidence assessment may reference a file with its stable token, for example `file:F001`. File references are fail-closed: if an assessment contains a `file:` reference, validation requires the exact evidence manifest:

```text
bidlint-supplier-evidence validate buyer-review.json evidence-assessment.json evidence-review.json \
  --evidence-files evidence-files.json
```

Validation confirms that the file token exists, is bound to the same requirement ID and is allowed for the evidence dimension where it is cited. The resulting `bidlint.supplier-evidence-review / 1` records canonical and byte provenance for the evidence-file manifest. A `file:` reference without `--evidence-files` is rejected.

## Pilot attestation and portal gate binding

When the validated evidence review is file-backed, the same exact evidence manifest must remain present through external-pilot attestation and portal-readiness evaluation:

```text
bidlint-supplier-pilot attestation-template \
  buyer-review.json evidence-review.json history.json pilot-attestation.json \
  --evidence-files evidence-files.json

bidlint-supplier-pilot portal-gate \
  buyer-review.json evidence-review.json history.json pilot-attestation.json portal-readiness.json \
  --evidence-files evidence-files.json
```

The attestation records `source_supplier_evidence_files_sha256`. The portal gate verifies that digest against the supplied manifest and against the evidence-review provenance. If the file-backed evidence review is supplied without `--evidence-files`, if the manifest was changed after human review, or if the attestation names another manifest digest, the workflow fails closed.

This keeps one immutable provenance chain:

`returned file bytes → evidence-files manifest → human evidence review → immutable history → pilot attestation → portal gate`

Evidence files remain external project-controlled bytes. BidLint does not upload, copy, approve or interpret the content merely because it is present in this manifest. Human evidence adequacy review remains mandatory.

This contract does not change technical compliance, supplier approval, deviation acceptance, contractual acceptance, or BidLint evaluator/scoring semantics.
