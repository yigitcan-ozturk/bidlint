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

Evidence files remain external project-controlled bytes. BidLint does not upload, copy, approve or interpret the content merely because it is present in this manifest. Human evidence adequacy review remains mandatory. Evidence assessment references may use the generated token form `file:F001`.

This contract does not change technical compliance, supplier approval, deviation acceptance, contractual acceptance, or BidLint evaluator/scoring semantics.
