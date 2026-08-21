from __future__ import annotations

import json

from bidlint.errors import ExitCode
from bidlint.pilot_init import initialize_workspace, main


def test_initialize_workspace_creates_private_first_scaffold(tmp_path):
    workspace = tmp_path / "pilot-workspace"

    result = initialize_workspace(workspace, pilot_id="external-pump-001", vendor_count=2)

    assert result["raw_gitignored"] is True
    assert result["ready_for_scan"] is False
    assert (workspace / "raw").is_dir()
    assert (workspace / "evidence").is_dir()
    assert (workspace / "review" / "TECHNICAL_REVIEW.md").is_file()
    assert (workspace / "review" / "approval.json").is_file()
    assert (workspace / "SANITIZATION_CHECKLIST.md").is_file()
    assert (workspace / "sanitized" / "specification").is_dir()
    assert (workspace / "sanitized" / "vendors" / "vendor-01").is_dir()
    assert (workspace / "sanitized" / "vendors" / "vendor-02").is_dir()

    manifest = json.loads((workspace / "pilot.json").read_text(encoding="utf-8"))
    assert manifest["pilot_id"] == "external-pump-001"
    assert manifest["repeats"] == 2
    assert manifest["vendors"] == [
        "sanitized/vendors/vendor-01/vendor.pdf",
        "sanitized/vendors/vendor-02/vendor.pdf",
    ]
    assert manifest["options"]["threshold"] == 0.52
    assert manifest["options"]["knockouts"] is None
    assert manifest["options"]["spec_xlsx_sheet"] is None
    assert manifest["options"]["xlsx_sheet"] is None

    approval = json.loads((workspace / "review" / "approval.json").read_text(encoding="utf-8"))
    assert approval["pilot_id"] == "external-pump-001"
    assert approval["sanitization"]["approved"] is False
    assert approval["technical"]["decision"] == "RE_RUN_AFTER_FIXES"
    assert approval["technical"]["all_non_pass_findings_reviewed"] is False

    gitignore = (workspace / ".gitignore").read_text(encoding="utf-8")
    assert "raw/" in gitignore
    assert "evidence/" in gitignore
    assert "review/" in gitignore


def test_initialize_workspace_refuses_nonempty_destination(tmp_path):
    workspace = tmp_path / "pilot-workspace"
    workspace.mkdir()
    marker = workspace / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")

    try:
        initialize_workspace(workspace, pilot_id="pilot-001")
    except ValueError as exc:
        assert "new or empty" in str(exc)
    else:
        raise AssertionError("non-empty workspace should be rejected")

    assert marker.read_text(encoding="utf-8") == "do not overwrite"


def test_initialize_workspace_rejects_sensitive_or_path_like_pilot_ids(tmp_path):
    for index, pilot_id in enumerate(("../customer", "customer name", "pilot@example.com", "/absolute")):
        workspace = tmp_path / f"pilot-workspace-{index}"
        try:
            initialize_workspace(workspace, pilot_id=pilot_id)
        except ValueError as exc:
            assert "pilot_id" in str(exc)
        else:
            raise AssertionError(f"unsafe pilot id accepted: {pilot_id}")


def test_cli_creates_json_result(tmp_path, capsys):
    workspace = tmp_path / "pilot-workspace"

    exit_code = main([str(workspace), "--pilot-id", "pilot-002", "--vendors", "3", "--json"])

    assert exit_code == int(ExitCode.SUCCESS)
    payload = json.loads(capsys.readouterr().out)
    assert payload["pilot_id"] == "pilot-002"
    assert payload["vendor_count"] == 3
    assert payload["ready_for_scan"] is False


def test_cli_returns_config_error_without_overwriting_existing_content(tmp_path, capsys):
    workspace = tmp_path / "pilot-workspace"
    workspace.mkdir()
    (workspace / "private.pdf").write_bytes(b"private")

    exit_code = main([str(workspace), "--pilot-id", "pilot-003"])

    assert exit_code == int(ExitCode.CONFIG)
    assert "new or empty" in capsys.readouterr().err
    assert (workspace / "private.pdf").read_bytes() == b"private"
