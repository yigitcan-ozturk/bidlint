from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .supplier_files import write_supplier_evidence_file_manifest
from .supplier_pilot import prepare_pilot_return


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def prepare_pilot_return_with_evidence_files(
    register_path: str | Path,
    response_path: str | Path,
    output_dir: str | Path,
    *,
    evidence_map_path: str | Path | None = None,
) -> dict:
    manifest = prepare_pilot_return(register_path, response_path, output_dir)
    if evidence_map_path is None:
        return manifest

    output = Path(output_dir)
    evidence_files_path = output / "evidence-files.json"
    evidence_files = write_supplier_evidence_file_manifest(
        output / "buyer-review.json",
        evidence_map_path,
        evidence_files_path,
    )
    evidence_files_bytes = evidence_files_path.read_bytes()

    pilot_manifest_path = output / "pilot-return-manifest.json"
    pilot_manifest = json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
    pilot_manifest["artifacts"]["evidence_files"] = {
        "path": evidence_files_path.name,
        "canonical_sha256": _canonical_json_sha256(evidence_files),
        "byte_sha256": _sha256_bytes(evidence_files_bytes),
        "file_count": evidence_files["file_count"],
    }
    pilot_manifest["next_action"] = (
        "complete evidence-assessment.json using file:Fxxx references where applicable; "
        "validate it with --evidence-files evidence-files.json, then create or append supplier history"
    )
    pilot_manifest_path.write_text(
        json.dumps(pilot_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pilot_manifest
