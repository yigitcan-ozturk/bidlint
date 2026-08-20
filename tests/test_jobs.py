import json
import threading
import time
import uuid
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from bidlint.jobs import JobManager, get_job_manager
from bidlint.mcp_server import get_job_result, submit_compare_job


def wait_for_status(manager: JobManager, job_id: str, wanted: set[str], timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = manager.status(job_id)
        if status["status"] in wanted:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {sorted(wanted)}")


def make_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 22
    c.save()


def test_job_completion_persists_result(tmp_path):
    manager = JobManager(tmp_path, max_workers=1)
    try:
        submitted = manager.submit(operation="test", request={"value": 3}, runner=lambda: {"answer": 6})
        job_id = submitted["job_id"]
        wait_for_status(manager, job_id, {"completed"})

        result = manager.result(job_id)
        assert result["status"] == "completed"
        assert result["result"] == {"answer": 6}
        assert result["error"] is None

        persisted = json.loads((tmp_path / ".bidlint" / "jobs" / f"{job_id}.json").read_text(encoding="utf-8"))
        assert persisted["status"] == "completed"
        assert persisted["result"] == {"answer": 6}
    finally:
        manager.shutdown()


def test_job_failure_is_pollable(tmp_path):
    manager = JobManager(tmp_path, max_workers=1)

    def fail() -> dict:
        raise RuntimeError("boom")

    try:
        submitted = manager.submit(operation="test", request={}, runner=fail)
        job_id = submitted["job_id"]
        wait_for_status(manager, job_id, {"failed"})
        result = manager.result(job_id)
        assert result["result"] is None
        assert result["error"] == "RuntimeError: boom"
    finally:
        manager.shutdown()


def test_queued_job_can_be_cancelled_before_execution(tmp_path):
    manager = JobManager(tmp_path, max_workers=1)
    release = threading.Event()
    started = threading.Event()

    def blocker() -> dict:
        started.set()
        release.wait(timeout=3)
        return {"done": True}

    try:
        first = manager.submit(operation="blocker", request={}, runner=blocker)
        assert started.wait(timeout=2)
        second = manager.submit(operation="queued", request={}, runner=lambda: {"should": "not run"})
        cancelled = manager.cancel(second["job_id"])
        assert cancelled["status"] == "cancelled"
        release.set()
        wait_for_status(manager, first["job_id"], {"completed"})
        assert manager.result(second["job_id"])["result"] is None
    finally:
        release.set()
        manager.shutdown()


def test_running_job_uses_cooperative_cancellation(tmp_path):
    manager = JobManager(tmp_path, max_workers=1)
    release = threading.Event()
    started = threading.Event()

    def slow() -> dict:
        started.set()
        release.wait(timeout=3)
        return {"completed_work": True}

    try:
        submitted = manager.submit(operation="slow", request={}, runner=slow)
        job_id = submitted["job_id"]
        assert started.wait(timeout=2)
        wait_for_status(manager, job_id, {"running"})
        cancellation = manager.cancel(job_id)
        assert cancellation["cancel_requested"] is True
        release.set()
        wait_for_status(manager, job_id, {"cancelled"})
        assert manager.result(job_id)["result"] is None
    finally:
        release.set()
        manager.shutdown()


def test_orphaned_running_job_is_failed_on_manager_restart(tmp_path):
    jobs_dir = tmp_path / ".bidlint" / "jobs"
    jobs_dir.mkdir(parents=True)
    job_id = uuid.uuid4().hex
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "operation": "compare",
        "status": "running",
        "submitted_at": "2026-08-20T00:00:00+00:00",
        "started_at": "2026-08-20T00:00:01+00:00",
        "finished_at": None,
        "cancel_requested": False,
        "request": {},
        "result": None,
        "error": None,
    }
    (jobs_dir / f"{job_id}.json").write_text(json.dumps(record), encoding="utf-8")

    manager = JobManager(tmp_path, max_workers=1)
    try:
        result = manager.result(job_id)
        assert result["status"] == "failed"
        assert result["error"] == "server restarted before job completed"
    finally:
        manager.shutdown()


def test_submit_compare_job_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    specification = tmp_path / "spec.pdf"
    vendor = tmp_path / "vendor.pdf"
    make_pdf(specification, ["Motor power shall be minimum 10 kW"])
    make_pdf(vendor, ["Motor power: 11000 W"])

    submitted = submit_compare_job("spec.pdf", "vendor.pdf")
    manager = get_job_manager(tmp_path)
    try:
        wait_for_status(manager, submitted["job_id"], {"completed"})
        result = get_job_result(submitted["job_id"])
        assert result["request"]["specification"] == "spec.pdf"
        assert result["request"]["vendor"] == "vendor.pdf"
        assert result["result"]["compliance_score"] == 100.0
        assert result["result"]["findings"][0]["status"] == "PASS"
    finally:
        manager.shutdown()
