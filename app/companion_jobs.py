"""Background image jobs + VRAM swap. Chat always preempts."""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from typing import Any

from app.companion_image import IMAGE_STEP_DEFAULT, append_day_log, day_output_dir
from app.llm import unload_model as unload_qwen

_LOCK = threading.Lock()
_QUEUE: deque[str] = deque()
_JOBS: dict[str, dict[str, Any]] = {}
_WORKER: threading.Thread | None = None
_WAKE = threading.Event()
_CANCEL = threading.Event()
_CHAT_STOP = threading.Event()
_CHATTING = threading.Event()
_CHAT_GEN = 0
_BUSY = threading.Event()
_RESOURCE = "ready"
_SESSION_AUTO = 0
_LAST_IMAGE_TS = 0.0
_LAST_SCENE: dict[str, str] = {}


def resource_state() -> str:
    return _RESOURCE


def image_busy() -> bool:
    with _LOCK:
        return any(j.get("status") in {"queued", "running"} for j in _JOBS.values())


def last_image_meta() -> dict[str, Any]:
    return {
        "last_ts": _LAST_IMAGE_TS,
        "auto_count": _SESSION_AUTO,
        "last_scene": dict(_LAST_SCENE),
        "resource": _RESOURCE,
    }


def begin_chat() -> int:
    """Take the GPU for chat. Wait for another device instead of killing their reply."""
    global _CHAT_GEN, _RESOURCE
    deadline = time.time() + 90
    while _CHATTING.is_set() and time.time() < deadline:
        time.sleep(0.12)
    _CHAT_GEN += 1
    gen = _CHAT_GEN
    _CHAT_STOP.clear()
    _CHATTING.set()
    preempt_for_chat()
    return gen


def chat_stop_requested(gen: int | None = None) -> bool:
    if gen is not None and gen != _CHAT_GEN:
        return True
    return _CHAT_STOP.is_set()


def preempt_for_chat() -> None:
    """Chat wins: ask the image worker to stop so Qwen can load."""
    global _RESOURCE
    _CANCEL.set()
    deadline = time.time() + 12
    while _BUSY.is_set() and time.time() < deadline:
        time.sleep(0.15)
    _RESOURCE = "chatting"


def chat_finished(gen: int | None = None) -> None:
    global _RESOURCE
    if gen is not None and gen != _CHAT_GEN:
        return
    _CHATTING.clear()
    _CANCEL.clear()
    if _BUSY.is_set():
        _RESOURCE = "generating_image"
    else:
        _RESOURCE = "ready"
    _WAKE.set()


def request_stop(*, job_id: str | None = None, chat: bool = True, image: bool = True) -> dict[str, Any]:
    """User stop: do not requeue cancelled manual jobs."""
    stopped = {"chat": False, "image": False}
    if chat:
        _CHAT_STOP.set()
        stopped["chat"] = True
    if image:
        _CANCEL.set()
        with _LOCK:
            if job_id:
                targets = [job_id]
            else:
                targets = [jid for jid, job in _JOBS.items() if job.get("status") in {"queued", "running"}]
            for jid in targets:
                job = _JOBS.get(jid)
                if not job:
                    continue
                job["user_stop"] = True
                if job.get("status") == "queued":
                    job["status"] = "cancelled"
                    job["error"] = "stopped"
                    try:
                        _QUEUE.remove(jid)
                    except ValueError:
                        pass
                stopped["image"] = True
    return stopped


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        out = dict(job)
    if out.get("status") == "running" and out.get("started"):
        out["elapsed"] = round(time.time() - float(out["started"]), 2)
    return out


def list_recent(limit: int = 8) -> list[dict[str, Any]]:
    with _LOCK:
        items = list(_JOBS.values())[-limit:]
    return [dict(j) for j in items]


def enqueue(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "error": "",
        "images": [],
        "debug": payload.get("debug") or {},
        "manual": bool(payload.get("manual")),
        "created": time.time(),
        "caption": str(payload.get("caption") or ""),
        "payload": payload,
    }
    with _LOCK:
        _JOBS[job_id] = job
        _QUEUE.append(job_id)
    _ensure_worker()
    _WAKE.set()
    return dict(job)


def _ensure_worker() -> None:
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return
    _WORKER = threading.Thread(target=_loop, name="companion-image", daemon=True)
    _WORKER.start()


def _loop() -> None:
    global _RESOURCE, _SESSION_AUTO, _LAST_IMAGE_TS, _LAST_SCENE
    while True:
        _WAKE.wait(timeout=0.5)
        _WAKE.clear()
        while True:
            with _LOCK:
                if not _QUEUE:
                    break
                job_id = _QUEUE.popleft()
                job = _JOBS.get(job_id)
            if not job:
                continue
            if job.get("user_stop"):
                job["status"] = "cancelled"
                job["error"] = "stopped"
                continue
            if _CHATTING.is_set():
                with _LOCK:
                    _QUEUE.appendleft(job_id)
                break
            if _CANCEL.is_set() and not job.get("manual"):
                job["status"] = "skipped"
                job["error"] = "skipped because chat needed the GPU"
                continue
            _run_job(job)


def _run_job(job: dict[str, Any]) -> None:
    global _RESOURCE, _SESSION_AUTO, _LAST_IMAGE_TS, _LAST_SCENE
    from app.companion_engine import attach_images, load_memory, save_memory, set_device
    from app.companion_sdxl import generate, sleep_pipeline, unload_pipeline

    payload = job["payload"]
    set_device(str(payload.get("device_id") or ""))
    if job.get("user_stop"):
        job["status"] = "cancelled"
        job["error"] = "stopped"
        return
    _BUSY.set()
    if not job.get("user_stop"):
        _CANCEL.clear()
    job["status"] = "running"
    job["phase"] = "loading"
    job["started"] = time.time()
    _RESOURCE = "loading_image"
    t0 = job["started"]
    try:
        if job.get("user_stop") or _CANCEL.is_set():
            raise RuntimeError("cancelled")
        unload_qwen()
        time.sleep(0.4)
        if job.get("user_stop") or _CANCEL.is_set():
            raise RuntimeError("cancelled")

        def on_phase(phase: str) -> None:
            global _RESOURCE
            job["phase"] = phase
            _RESOURCE = "generating_image" if phase == "drawing" else "loading_image"

        images = generate(
            prompt=payload["prompt"],
            negative_prompt=payload["negative"],
            width=int(payload.get("width") or 768),
            height=int(payload.get("height") or 1152),
            steps=int(payload.get("steps") or IMAGE_STEP_DEFAULT),
            guidance=float(payload.get("cfg") or 4),
            seed=int(payload.get("seed") or -1),
            count=int(payload.get("count") or 1),
            checkpoint=payload.get("checkpoint"),
            accel=payload.get("accel") or "none",
            out_dir=day_output_dir(),
            cancel=_CANCEL.is_set,
            on_phase=on_phase,
        )
        job["images"] = images
        job["status"] = "done"
        job["seconds"] = round(time.time() - t0, 2)
        try:
            attach_images(job["id"], images)
        except Exception:
            pass
        try:
            append_day_log(images, payload, job["seconds"])
        except Exception:
            pass
        job["debug"] = {
            **(job.get("debug") or {}),
            "prompt": payload.get("prompt"),
            "negative": payload.get("negative"),
            "checkpoint": (images[0].get("checkpoint") if images else payload.get("checkpoint")),
            "accel": payload.get("accel"),
            "width": payload.get("width"),
            "height": payload.get("height"),
            "steps": payload.get("steps"),
            "cfg": payload.get("cfg"),
            "seed": images[0].get("seed") if images else payload.get("seed"),
            "seconds": job["seconds"],
            "resource": "ok",
        }
        _LAST_IMAGE_TS = time.time()
        scene = payload.get("scene") or {}
        _LAST_SCENE = dict(scene)
        if not payload.get("manual"):
            _SESSION_AUTO += 1
    except Exception as exc:
        job["status"] = "error" if "cancel" not in str(exc).lower() else "cancelled"
        job["error"] = str(exc)
        job["seconds"] = round(time.time() - t0, 2)
    finally:
        try:
            sleep_pipeline()
        except Exception:
            try:
                unload_pipeline()
            except Exception:
                pass
        if (
            job["status"] == "cancelled"
            and payload.get("manual")
            and not job.get("user_stop")
        ):
            job["status"] = "queued"
            job["error"] = ""
            with _LOCK:
                _QUEUE.append(job["id"])
            _WAKE.set()
        elif job.get("user_stop") and job["status"] == "cancelled":
            job["error"] = "stopped"
        _BUSY.clear()
        _RESOURCE = "ready"


def reset_session_caps() -> None:
    global _SESSION_AUTO
    _SESSION_AUTO = 0
