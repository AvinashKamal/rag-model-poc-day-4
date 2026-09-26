"""In-memory tracker for ingestion runs, keyed by run_id.

POC scope: a plain dict guarded by a lock is enough. No persistence across
process restarts — an in-flight run_id is lost if the backend process
restarts mid-run, which is an accepted tradeoff for this milestone (the task
spec explicitly allows this: "no need for persistence across process
restarts unless trivial to add").
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, Literal

Status = Literal["running", "done", "failed"]

_lock = threading.Lock()
_runs: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_run(run_id: str) -> None:
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "status": "running",
            "result": None,
            "error": None,
            "created_at": _now(),
            "updated_at": _now(),
        }


def mark_done(run_id: str, result: dict) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is None:
            return
        run["status"] = "done"
        run["result"] = result
        run["updated_at"] = _now()


def mark_failed(run_id: str, error: str) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run is None:
            return
        run["status"] = "failed"
        run["error"] = error
        run["updated_at"] = _now()


def get_run(run_id: str) -> dict[str, Any] | None:
    with _lock:
        run = _runs.get(run_id)
        return dict(run) if run is not None else None
