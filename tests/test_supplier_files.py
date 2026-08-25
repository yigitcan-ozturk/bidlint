import hashlib
import json
from pathlib import Path

import pytest

from bidlint.supplier_files_cli import main


def _review() -> dict:
    return {
        "contract": "bidlint.supplier-clarification-review",
        "contract_version": "1",
        "tool": "bidlint",
        "version": "1.2.0.dev0",
        "specification": "317L-rfq.pdf",
        "vendor": "supplier-offer.xlsx",
        "review_status": "PENDING_REVIEW",
        "automatic_acceptance": False,
        "human_review_required": True,
        "items": [
            {
                "requirement_id": "R0001",
                "parameter": "material grade",
                "prior_finding_status": "REVIEW",
            },
            {
                "requirement_id": "R0002",
                "parameter": "ultrasonic test",
                "prior_finding_status": "MISSING",
            },
        ],
    }


def _write_review(tmp_path: Path) -> Path:
    path = tmp_path / "buyer-review.json"
    path.write_text(json.dumps(_review()), encoding="utf-8")
    return path


def test_supplier_files_cli_records_exact_byte_provenance(tmp_path: Path):
    review_path = _write_review(tmp_path)
    evidence = tmp_path / "MTC-317L.pdf"
    evidence.write_bytes(b"certificate-bytes\x00\x01")
    evidence_map = tmp_path / "evidence-map.json"
    evidence_map.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": evidence.name,
                        "requirement_ids": ["R0001", "R0002"],
                        "evidence_types": ["certificate", "test_basis"],
                        "note": "returned with clarification",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "evidence-files.json"

    assert main([str(review_path), str(evidence_map), str(output)]) == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))

    assert manifest["contract"] == "bidlint.supplier-evidence-files"
    assert manifest["file_count"] == 1
    assert manifest["automatic_acceptance"] is False
    assert manifest["human_review_required"] is True
    assert manifest["affects_evaluator"] is False
    assert manifest["content_interpreted"] is False
    assert manifest["files_copied"] is False
    item = manifest["files"][0]
    assert item["file_id"] == "F001"
    assert item["reference"] == "file:F001"
    assert item["name"] == evidence.name
    assert item["byte_sha256"] == hashlib.sha256(evidence.read_bytes()).hexdigest()
    assert item["byte_length"] == len(evidence.read_bytes())
    assert item["requirement_ids"] == ["R0001", "R0002"]
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


def test_supplier_files_rejects_unknown_requirement_binding(tmp_path: Path):
    review_path = _write_review(tmp_path)
    evidence = tmp_path / "cert.pdf"
    evidence.write_bytes(b"cert")
    evidence_map = tmp_path / "evidence-map.json"
    evidence_map.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": evidence.name,
                        "requirement_ids": ["R9999"],
                        "evidence_types": ["certificate"],
                        "note": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="unknown requirement_id binding"):
        main([str(review_path), str(evidence_map), str(tmp_path / "out.json")])


def test_supplier_files_rejects_unsupported_evidence_type(tmp_path: Path):
    review_path = _write_review(tmp_path)
    evidence = tmp_path / "cert.pdf"
    evidence.write_bytes(b"cert")
    evidence_map = tmp_path / "evidence-map.json"
    evidence_map.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": evidence.name,
                        "requirement_ids": ["R0001"],
                        "evidence_types": ["marketing_brochure"],
                        "note": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="unsupported evidence_type"):
        main([str(review_path), str(evidence_map), str(tmp_path / "out.json")])


def test_supplier_files_rejects_missing_file(tmp_path: Path):
    review_path = _write_review(tmp_path)
    evidence_map = tmp_path / "evidence-map.json"
    evidence_map.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "missing.pdf",
                        "requirement_ids": ["R0001"],
                        "evidence_types": ["certificate"],
                        "note": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="evidence file does not exist"):
        main([str(review_path), str(evidence_map), str(tmp_path / "out.json")])
