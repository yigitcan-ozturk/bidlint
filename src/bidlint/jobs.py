from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_VALID_STATUSES = {"queued", "running", *_TERMINAL_STATUSES}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worker_count() -> int:
    raw = os.environ.get("BIDLINT_MCP_JOB_WORKERS", "2")
    try:
        count = int(raw)
    except ValueError as exc:
        raise ValueError("BIDLINT_MCP_JOB_WORKERS must be an integer") from exc
    if not 1 <= count <= 8:
        raise ValueError("BIDLINT_MCP_JOB_WORKERS must be between 1 and 8")
    return count


class JobManager:
    """Small local job state machine for long-running deterministic document work.

    Job metadata and terminal results are persisted as JSON under the configured
    MCP root. Active work runs in a bounded thread pool. Running work is not
    resumed after a server restart; orphaned jobs are marked failed explicitly.
    """

    def __init__(self, root: Path, *, max_workers: int | None = None) -> None:
        self.root = root.resolve()
        self.jobs_dir = self.root / ".bidlint" / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        resolved_jobs_dir = self.jobs_dir.resolve()
        if not resolved_jobs_dir.is_relative_to(self.root):
            raise ValueError("job directory must stay within MCP root")
        self.jobs_dir = resolved_jobs_dir
        self._lock = threading.RLock()
        self._futures: dict[str, Future[Any]] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers if max_workers is not None else _worker_count(),
            thread_name_prefix="bidlint-job",
        )
        self._recover_orphans()

    def _job_path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or len(job_id) != 32 or any(ch not in "0123456789abcdef" for ch in job_id):
            raise ValueError("invalid job_id")
        return self.jobs_dir / f"{job_id}.json"

    def _read_unlocked(self, job_id: str) -> dict[str, Any]:
        path = self._job_path(job_id)
        if not path.is_file():
            raise ValueError(f"job not found: {job_id}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to read job: {job_id}") from exc
        if data.get("job_id") != job_id or data.get("status") not in _VALID_STATUSES:
            raise ValueError(f"invalid job record: {job_id}")
        return data

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        job_id = data["job_id"]
        path = self._job_path(job_id)
        temporary = path.with_suffix(".tmp")
        payload = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(path)

    def _recover_orphans(self) -> None:
        with self._lock:
            for path in self.jobs_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if data.get("status") not in {"queued", "running"}:
                    continue
                data["status"] = "failed"
                data["finished_at"] = _utc_now()
                data["error"] = "server restarted before job completed"
                data["cancel_requested"] = False
                self._write_unlocked(data)

    def submit(
        self,
        *,
        operation: str,
        request: dict[str, Any],
        runner: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("operation is required")
        job_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "schema_version": 1,
            "job_id": job_id,
            "operation": operation.strip(),
            "status": "queued",
            "submitted_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "cancel_requested": False,
            "request": request,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._write_unlocked(record)
            future = self._executor.submit(self._run, job_id, runner)
            self._futures[job_id] = future
        return self.status(job_id)

    def _run(self, job_id: str, runner: Callable[[], dict[str, Any]]) -> None:
        with self._lock:
            record = self._read_unlocked(job_id)
            if record["status"] == "cancelled" or record.get("cancel_requested"):
                record["status"] = "cancelled"
                record["finished_at"] = _utc_now()
                self._write_unlocked(record)
                return
            record["status"] = "running"
            record["started_at"] = _utc_now()
            self._write_unlocked(record)

        try:
            result = runner()
        except Exception as exc:  # job boundary must capture deterministic/parser failures for polling
            with self._lock:
                record = self._read_unlocked(job_id)
                if record.get("cancel_requested"):
                    record["status"] = "cancelled"
                    record["error"] = None
                else:
                    record["status"] = "failed"
                    record["error"] = f"{type(exc).__name__}: {exc}"
                record["result"] = None
                record["finished_at"] = _utc_now()
                self._write_unlocked(record)
            return

        with self._lock:
            record = self._read_unlocked(job_id)
            if record.get("cancel_requested"):
                record["status"] = "cancelled"
                record["result"] = None
            else:
                record["status"] = "completed"
                record["result"] = result
            record["error"] = None
            record["finished_at"] = _utc_now()
            self._write_unlocked(record)

    def status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._read_unlocked(job_id)
            return {
                "job_id": record["job_id"],
                "operation": record["operation"],
                "status": record["status"],
                "submitted_at": record["submitted_at"],
                "started_at": record["started_at"],
                "finished_at": record["finished_at"],
                "cancel_requested": bool(record.get("cancel_requested")),
            }

    def result(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._read_unlocked(job_id)
            return {
                **self.status(job_id),
                "request": record["request"],
                "result": record["result"] if record["status"] == "completed" else None,
                "error": record["error"] if record["status"] == "failed" else None,
            }

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._read_unlocked(job_id)
            if record["status"] in _TERMINAL_STATUSES:
                return self.status(job_id)

            record["cancel_requested"] = True
            future = self._futures.get(job_id)
            if record["status"] == "queued" and future is not None and future.cancel():
                record["status"] = "cancelled"
                record["finished_at"] = _utc_now()
            self._write_unlocked(record)
            return self.status(job_id)


_MANAGERS: dict[Path, JobManager] = {}
_MANAGERS_LOCK = threading.Lock()


def get_job_manager(root: Path) -> JobManager:
    resolved = root.resolve()
    with _MANAGERS_LOCK:
        manager = _MANAGERS.get(resolved)
        if manager is None:
            manager = JobManager(resolved)
            _MANAGERS[resolved] = manager
        return manager
