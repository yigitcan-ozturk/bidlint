from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from pathlib import Path

from . import __version__

_SOURCE_CONTRACT = "bidlint.lab-pilot-source-manifest"
_FREEZE_CONTRACT = "bidlint.lab-pilot-blind-freeze"
_CONTRACT_VERSION = "1"
_FREEZE_ID = "BLIND_SCORE_FREEZE_001"

_SOURCE_ROLES = {
    "layout_requirement",
    "supplier_quotation",
    "comparison_spreadsheet",
    "technical_presentation",
    "technical_evidence",
}
_FREEZE_ROLES = {
    "requirement_register",
    "layout_boq_binding",
    "technical_compliance",
    "commercial_normalization",
    "material_fit",
    "clarification_register",
}
_REQUIRED_FREEZE_ROLES = {
    "technical_compliance",
    "commercial_normalization",
    "material_fit",
}
_BLIND_SUPPLIER = re.compile(r"^Supplier-[A-Z]$")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _require_string(mapping: dict, key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _read_json_object(path: str | Path, label: str) -> tuple[dict, bytes, Path]:
    source = Path(path)
    data = source.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload, data, source


def _resolve_file(base_dir: str | Path, raw_path: str, label: str) -> Path:
    source = Path(raw_path)
    if not source.is_absolute():
        source = Path(base_dir) / source
    resolved = source.resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {raw_path}")
    if not resolved.is_file():
        raise ValueError(f"{label} is not a file: {raw_path}")
    return resolved


def build_source_manifest(source_map: dict, *, base_dir: str | Path) -> dict:
    case_id = _require_string(source_map, "case_id")
    entries = source_map.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValueError("sources must be a non-empty list")

    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    sources: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("source entries must be JSON objects")
        source_id = _require_string(entry, "source_id")
        role = _require_string(entry, "role")
        raw_path = _require_string(entry, "path")
        if source_id in seen_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        seen_ids.add(source_id)
        if role not in _SOURCE_ROLES:
            raise ValueError(f"unsupported source role: {role}")

        resolved = _resolve_file(base_dir, raw_path, "source file")
        if resolved in seen_paths:
            raise ValueError(f"duplicate source path: {raw_path}")
        seen_paths.add(resolved)
        data = resolved.read_bytes()
        media_type, _ = mimetypes.guess_type(resolved.name)
        sources.append(
            {
                "source_id": source_id,
                "role": role,
                "byte_sha256": _sha256_bytes(data),
                "byte_length": len(data),
                "media_type": media_type,
            }
        )

    return {
        "contract": _SOURCE_CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "case_id": case_id,
        "source_count": len(sources),
        "raw_files_embedded": False,
        "source_paths_persisted": False,
        "source_names_persisted": False,
        "content_interpreted": False,
        "human_review_required": True,
        "affects_evaluator": False,
        "sources": sources,
    }


def write_source_manifest(source_map_path: str | Path, output_path: str | Path) -> dict:
    source_map, source_map_bytes, source_map_file = _read_json_object(source_map_path, "source map")
    manifest = build_source_manifest(source_map, base_dir=source_map_file.parent)
    manifest["provenance"] = {
        "source_map": {
            "byte_sha256": _sha256_bytes(source_map_bytes),
            "byte_length": len(source_map_bytes),
        }
    }
    Path(output_path).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def build_blind_freeze(freeze_map: dict, *, base_dir: str | Path) -> dict:
    case_id = _require_string(freeze_map, "case_id")
    suppliers = freeze_map.get("suppliers")
    if not isinstance(suppliers, list) or not suppliers:
        raise ValueError("suppliers must be a non-empty list")
    if not all(isinstance(value, str) and _BLIND_SUPPLIER.fullmatch(value) for value in suppliers):
        raise ValueError("suppliers must use blind identifiers such as Supplier-A")
    if len(set(suppliers)) != len(suppliers):
        raise ValueError("duplicate blind supplier identifier")

    entries = freeze_map.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise ValueError("artifacts must be a non-empty list")

    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    roles_present: set[str] = set()
    artifacts: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("artifact entries must be JSON objects")
        artifact_id = _require_string(entry, "artifact_id")
        role = _require_string(entry, "role")
        raw_path = _require_string(entry, "path")
        if artifact_id in seen_ids:
            raise ValueError(f"duplicate artifact_id: {artifact_id}")
        seen_ids.add(artifact_id)
        if role not in _FREEZE_ROLES:
            raise ValueError(f"unsupported blind-freeze artifact role: {role}")
        if role in roles_present:
            raise ValueError(f"duplicate blind-freeze artifact role: {role}")
        roles_present.add(role)

        resolved = _resolve_file(base_dir, raw_path, "blind-freeze artifact")
        if resolved in seen_paths:
            raise ValueError(f"duplicate blind-freeze artifact path: {raw_path}")
        seen_paths.add(resolved)
        data = resolved.read_bytes()
        canonical_sha256: str | None = None
        if resolved.suffix.casefold() == ".json":
            parsed = json.loads(data.decode("utf-8"))
            canonical_sha256 = _canonical_json_sha256(parsed)
        media_type, _ = mimetypes.guess_type(resolved.name)
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "role": role,
                "byte_sha256": _sha256_bytes(data),
                "byte_length": len(data),
                "canonical_json_sha256": canonical_sha256,
                "media_type": media_type,
            }
        )

    missing_roles = sorted(_REQUIRED_FREEZE_ROLES - roles_present)
    if missing_roles:
        raise ValueError("blind freeze missing required artifact roles: " + ", ".join(missing_roles))

    return {
        "contract": _FREEZE_CONTRACT,
        "contract_version": _CONTRACT_VERSION,
        "tool": "bidlint",
        "version": __version__,
        "case_id": case_id,
        "freeze_id": _FREEZE_ID,
        "frozen": True,
        "supplier_identity_mode": "BLIND",
        "suppliers": suppliers,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "automatic_award": False,
        "automatic_identity_reveal": False,
        "buyer_identity_reveal_may_begin_after_freeze": True,
        "human_review_required": True,
        "affects_evaluator": False,
        "evaluator_semantics_changed": False,
    }


def write_blind_freeze(freeze_map_path: str | Path, output_path: str | Path) -> dict:
    freeze_map, freeze_map_bytes, freeze_map_file = _read_json_object(freeze_map_path, "blind freeze map")
    freeze = build_blind_freeze(freeze_map, base_dir=freeze_map_file.parent)
    freeze["provenance"] = {
        "freeze_map": {
            "byte_sha256": _sha256_bytes(freeze_map_bytes),
            "byte_length": len(freeze_map_bytes),
        }
    }
    Path(output_path).write_text(json.dumps(freeze, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return freeze
