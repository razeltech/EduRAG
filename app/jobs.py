"""Background index jobs so a Unity docs tree does not freeze the UI."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from app.db import new_id

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def start_index_job(
    path: Path,
    course_name: str,
    *,
    institution_id: str,
    max_files: int | None = None,
) -> dict[str, Any]:
    job_id = new_id()
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "running",
            "path": str(path),
            "course": course_name,
            "file_count": 0,
            "error": None,
        }

    def run() -> None:
        from app.pipeline import index_path

        try:
            result = index_path(
                path,
                course_name,
                institution_id=institution_id,
                max_files=max_files,
            )
            with _lock:
                _jobs[job_id].update(
                    {
                        "status": "done",
                        "file_count": len(result.get("documents") or []),
                        "course": (result.get("course") or {}).get("name") or course_name,
                    }
                )
        except Exception as exc:
            with _lock:
                _jobs[job_id].update({"status": "error", "error": str(exc)})

    threading.Thread(target=run, daemon=True).start()
    return get_job(job_id) or {"id": job_id, "status": "running"}
