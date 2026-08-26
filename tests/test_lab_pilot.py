from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bidlint.lab_pilot import build_blind_freeze, build_source_manifest, write_blind_freeze, write_source_manifest
from bidlint.lab_pilot_cli import main


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_source_manifest_omits_source_names_and_paths(tmp_path: Path) -> None:
    source = tmp_path / "Real Supplier Name - quotation.pdf"
    source.write_bytes(b"confidential quotation bytes")
    source_map = {
        "case_id": "lab-furniture-case-001",
        "sources": [{"source_id": "SRC-001", "role": "supplier_quotation", "path": source.name}],
    }

    manifest = build_source_manifest(source_map, base_dir=tmp_path)

    assert manifest["contract"] == "bidlint.lab-pilot-source-manifest"
    assert manifest["source_paths_persisted"] is False
    assert manifest["source_names_persisted"] is False
    assert manifest["content_interpreted"] is False
    assert manifest["affects_evaluator"] is False
    assert manifest["sources"] == [
        {
            "source_id": "SRC-001",
            "role": "supplier_quotation",
            "byte_sha256": _sha256(b"confidential quotation bytes"),
            "byte_length": len(b"confidential quotation bytes"),
            "media_type": "application/pdf",
        }
    ]
    assert source.name not in json.dumps(manifest)


def test_source_manifest_rejects_duplicate_source_path(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"x")
    source_map = {
        "case_id": "lab-furniture-case-001",
        "sources": [
            {"source_id": "SRC-001", "role": "layout_requirement", "path": source.name},
            {"source_id": "SRC-002", "role": "technical_evidence", "path": source.name},
        ],
    }

    with pytest.raises(ValueError, match="duplicate source path"):
        build_source_manifest(source_map, base_dir=tmp_path)


def test_blind_freeze_binds_required_artifacts_and_preserves_boundaries(tmp_path: Path) -> None:
    technical = tmp_path / "technical.json"
    commercial = tmp_path / "commercial.json"
    material = tmp_path / "material.json"
    technical.write_text('{"Supplier-A":"REVIEW"}\n', encoding="utf-8")
    commercial.write_text('{"Supplier-A":{"normalized":100}}\n', encoding="utf-8")
    material.write_text('{"Supplier-A":{"fit":"PARTIAL"}}\n', encoding="utf-8")

    freeze_map = {
        "case_id": "lab-furniture-case-001",
        "suppliers": ["Supplier-A", "Supplier-B"],
        "artifacts": [
            {"artifact_id": "ART-001", "role": "technical_compliance", "path": technical.name},
            {"artifact_id": "ART-002", "role": "commercial_normalization", "path": commercial.name},
            {"artifact_id": "ART-003", "role": "material_fit", "path": material.name},
        ],
    }

    freeze = build_blind_freeze(freeze_map, base_dir=tmp_path)

    assert freeze["contract"] == "bidlint.lab-pilot-blind-freeze"
    assert freeze["freeze_id"] == "BLIND_SCORE_FREEZE_001"
    assert freeze["frozen"] is True
    assert freeze["supplier_identity_mode"] == "BLIND"
    assert freeze["automatic_award"] is False
    assert freeze["automatic_identity_reveal"] is False
    assert freeze["buyer_identity_reveal_may_begin_after_freeze"] is True
    assert freeze["human_review_required"] is True
    assert freeze["affects_evaluator"] is False
    assert freeze["evaluator_semantics_changed"] is False
    assert {artifact["role"] for artifact in freeze["artifacts"]} == {
        "technical_compliance",
        "commercial_normalization",
        "material_fit",
    }
    assert all(artifact["canonical_json_sha256"] for artifact in freeze["artifacts"])


def test_blind_freeze_rejects_real_supplier_identity(tmp_path: Path) -> None:
    for name in ("technical.json", "commercial.json", "material.json"):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    freeze_map = {
        "case_id": "lab-furniture-case-001",
        "suppliers": ["Real Supplier Ltd"],
        "artifacts": [
            {"artifact_id": "ART-001", "role": "technical_compliance", "path": "technical.json"},
            {"artifact_id": "ART-002", "role": "commercial_normalization", "path": "commercial.json"},
            {"artifact_id": "ART-003", "role": "material_fit", "path": "material.json"},
        ],
    }

    with pytest.raises(ValueError, match="blind identifiers"):
        build_blind_freeze(freeze_map, base_dir=tmp_path)


def test_blind_freeze_requires_all_three_decision_artifacts(tmp_path: Path) -> None:
    technical = tmp_path / "technical.json"
    technical.write_text("{}\n", encoding="utf-8")
    freeze_map = {
        "case_id": "lab-furniture-case-001",
        "suppliers": ["Supplier-A"],
        "artifacts": [{"artifact_id": "ART-001", "role": "technical_compliance", "path": technical.name}],
    }

    with pytest.raises(ValueError, match="commercial_normalization, material_fit"):
        build_blind_freeze(freeze_map, base_dir=tmp_path)


def test_writers_bind_map_bytes_and_cli_runs(tmp_path: Path) -> None:
    source = tmp_path / "layout.pdf"
    source.write_bytes(b"layout")
    source_map_path = tmp_path / "source-map.json"
    source_map_path.write_text(
        json.dumps(
            {
                "case_id": "lab-furniture-case-001",
                "sources": [{"source_id": "SRC-001", "role": "layout_requirement", "path": source.name}],
            }
        ),
        encoding="utf-8",
    )
    source_output = tmp_path / "source-manifest.json"

    assert main(["source-manifest", str(source_map_path), str(source_output)]) == 0
    source_manifest = json.loads(source_output.read_text(encoding="utf-8"))
    assert source_manifest["provenance"]["source_map"]["byte_sha256"] == _sha256(source_map_path.read_bytes())

    artifacts = []
    for index, role in enumerate(("technical_compliance", "commercial_normalization", "material_fit"), start=1):
        artifact = tmp_path / f"artifact-{index}.json"
        artifact.write_text("{}\n", encoding="utf-8")
        artifacts.append({"artifact_id": f"ART-{index:03d}", "role": role, "path": artifact.name})
    freeze_map_path = tmp_path / "freeze-map.json"
    freeze_map_path.write_text(
        json.dumps({"case_id": "lab-furniture-case-001", "suppliers": ["Supplier-A"], "artifacts": artifacts}),
        encoding="utf-8",
    )
    freeze_output = tmp_path / "blind-freeze.json"

    freeze = write_blind_freeze(freeze_map_path, freeze_output)
    assert freeze["provenance"]["freeze_map"]["byte_sha256"] == _sha256(freeze_map_path.read_bytes())
    assert freeze_output.exists()

    direct_source_output = tmp_path / "source-manifest-direct.json"
    written = write_source_manifest(source_map_path, direct_source_output)
    assert written["source_count"] == 1
