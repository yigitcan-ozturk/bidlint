# Private pilot intake workspace

BidLint 1.1 can create a private-first workspace for a real external pilot without copying any source documents into the repository:

```bash
bidlint-pilot-init ./pilot-workspace \
  --pilot-id external-pump-001 \
  --vendors 2
```

The command accepts only a new or empty destination. It refuses to overwrite existing content.

## Generated structure

```text
pilot-workspace/
├── .gitignore
├── README.md
├── SANITIZATION_CHECKLIST.md
├── pilot.json
├── raw/                         # git-ignored
├── sanitized/
│   ├── specification/
│   └── vendors/
│       ├── vendor-01/
│       └── vendor-02/
├── evidence/                    # git-ignored
└── review/                      # git-ignored
    └── TECHNICAL_REVIEW.md
```

`raw/` is for original external/customer material and is ignored by git from the moment the workspace is created. `evidence/` and `review/` are also ignored by default because hashes, filenames and human notes can still expose project context even when source documents are not present.

The `sanitized/` tree is the only intended candidate for later publication, and only after the generated checklist plus `bidlint-pilot-scan` and manual visual review have been completed.

## Manifest template

`pilot.json` is generated with generic placeholder paths, two repeat runs and the standard matching threshold. It contains no commercial settings and no inferred knockout policy.

A one-vendor workspace is a compare pilot. Two or more vendor slots become a rank pilot after the placeholder paths are populated with supported sanitized inputs or package directories.

The pilot ID is deliberately restricted to a short ASCII-safe token so names, email addresses or path traversal strings are not accidentally used as persistent evidence identifiers.

## Recommended sequence

```bash
bidlint-pilot-init ./pilot-workspace --pilot-id external-pump-001 --vendors 2
cd pilot-workspace
# place originals only under raw/
# create sanitized copies under sanitized/
bidlint-pilot-scan pilot.json --json --output evidence/sanitization-scan.json
bidlint-pilot pilot.json --json --output evidence/pilot-evidence.json
```

Then complete `review/TECHNICAL_REVIEW.md`, convert any reproducible false positive/false negative into a minimized sanitized regression fixture, approve the pilot evidence as a baseline, and verify a fresh replay with `bidlint-pilot-verify`.

## Security boundary

The intake command does not sanitize documents and does not move/copy any user files. It only creates an empty structure, a strict manifest template and checklists. The external pilot gate is not complete until actual sanitized inputs pass automated and human review.
