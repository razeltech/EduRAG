"""Chat LLM via Ollama — catalog + active model (Qwen default, gpt-oss optional)."""
from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.config_load import CONFIG_PATH, ROOT, load_config

# Built-in catalog. config.yaml can override / extend under llm.models.
DEFAULT_MODELS: list[dict[str, Any]] = [
    {
        "id": "qwen2.5:7b-instruct",
        "label": "Qwen 2.5 7B Instruct",
        "ollama_name": "qwen2.5:7b-instruct",
        "num_ctx": 4096,
        "num_predict": 2048,
        "temperature": 0.3,
        "keep_alive": "5m",
        "num_thread": 4,
        "num_batch": 256,
        # Full GPU fit on RTX 3060 12GB — leave num_gpu unset (Ollama auto).
        "notes": "Default. Fits RTX 3060 12GB VRAM.",
    },
    {
        "id": "gpt-oss:20b",
        "label": "GPT-OSS 20B (OpenAI)",
        "ollama_name": "gpt-oss:20b",
        "num_ctx": 2048,
        "num_predict": 1536,
        "temperature": 0.3,
        "keep_alive": "2m",
        "num_thread": 6,
        "num_batch": 128,
        # ~16GB recommended; on 12GB VRAM Ollama spills layers to system RAM.
        # Lower ctx keeps KV cache smaller so more layers stay on GPU.
        "notes": (
            "Optional only — not recommended on RTX 3060 12GB (slow RAM spill). "
            "Prefer Qwen 7B for daily chat. Pull only if you insist: ollama pull gpt-oss:20b."
        ),
    },
]

_CFG_LOCK = threading.Lock()
_PULL_LOCK = threading.Lock()
_pull_status: dict[str, Any] = {"running": False, "model": None, "log": "", "ok": None}


class OllamaError(RuntimeError):
    pass


def _merge_catalog(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    llm = cfg.get("llm") or {}
    custom = llm.get("models")
    if not isinstance(custom, list) or not custom:
        return deepcopy(DEFAULT_MODELS)
    by_id: dict[str, dict[str, Any]] = {m["id"]: deepcopy(m) for m in DEFAULT_MODELS if m.get("id")}
    for row in custom:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        mid = str(row["id"])
        base = by_id.get(mid, {"id": mid, "ollama_name": mid, "label": mid})
        merged = {**base, **{k: v for k, v in row.items() if v is not None}}
        if not merged.get("ollama_name"):
            merged["ollama_name"] = mid
        by_id[mid] = merged
    # Preserve default order, then any extra custom ids.
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in DEFAULT_MODELS:
        mid = m["id"]
        if mid in by_id:
            ordered.append(by_id[mid])
            seen.add(mid)
    for mid, row in by_id.items():
        if mid not in seen:
            ordered.append(row)
    return ordered


def list_models() -> list[dict[str, Any]]:
    cfg = load_config()
    active = ((cfg.get("llm") or {}).get("model") or "qwen2.5:7b-instruct").strip()
    installed = set(ollama_installed_names())
    out = []
    for m in _merge_catalog(cfg):
        name = m.get("ollama_name") or m["id"]
        out.append(
            {
                **m,
                "active": m["id"] == active or name == active,
                "installed": name in installed or m["id"] in installed,
            }
        )
    return out


def get_model_entry(model_id: str | None = None) -> dict[str, Any]:
    cfg = load_config()
    active = (model_id or (cfg.get("llm") or {}).get("model") or "qwen2.5:7b-instruct").strip()
    catalog = _merge_catalog(cfg)
    for m in catalog:
        if m["id"] == active or m.get("ollama_name") == active:
            return m
    # Unknown id still works if Ollama has it — use active string as ollama name.
    return {
        "id": active,
        "label": active,
        "ollama_name": active,
        "num_ctx": int((cfg.get("llm") or {}).get("num_ctx") or 4096),
        "num_predict": int((cfg.get("llm") or {}).get("num_predict") or 2048),
        "temperature": float((cfg.get("llm") or {}).get("temperature") or 0.3),
        "keep_alive": (cfg.get("llm") or {}).get("keep_alive") or "5m",
        "num_thread": 4,
        "num_batch": 256,
        "notes": "Not in built-in catalog; using config defaults.",
    }


def llm_settings(model_id: str | None = None) -> dict:
    cfg = load_config()
    llm = cfg.get("llm") or {}
    res = cfg.get("resources") or {}
    entry = get_model_entry(model_id)
    keep = (
        entry.get("keep_alive")
        or llm.get("keep_alive")
        or res.get("ollama_keep_alive")
        or "5m"
    )
    ollama_name = entry.get("ollama_name") or entry["id"]
    settings = {
        "base_url": llm.get("base_url") or "http://localhost:11434",
        "model": ollama_name,
        "model_id": entry["id"],
        "label": entry.get("label") or entry["id"],
        "temperature": float(
            entry["temperature"]
            if entry.get("temperature") is not None
            else (llm.get("temperature") or 0.3)
        ),
        "num_ctx": int(entry.get("num_ctx") or llm.get("num_ctx") or 4096),
        "num_predict": int(entry.get("num_predict") or llm.get("num_predict") or 2048),
        "keep_alive": keep,
        "num_thread": int(
            entry.get("num_thread")
            or res.get("llm_threads")
            or llm.get("num_thread")
            or 4
        ),
        "num_batch": int(
            entry.get("num_batch") or res.get("llm_batch") or llm.get("num_batch") or 256
        ),
    }
    # Optional explicit GPU layer count (Ollama option). None = auto offload.
    if entry.get("num_gpu") is not None:
        settings["num_gpu"] = int(entry["num_gpu"])
    return settings


def ollama_installed_names() -> list[str]:
    s = llm_settings()
    url = s["base_url"].rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            if resp.status_code >= 400:
                return []
            data = resp.json()
    except Exception:
        return _ollama_list_cli()
    names = []
    for row in data.get("models") or []:
        name = (row.get("name") or "").strip()
        if name:
            names.append(name)
            # Also accept bare tag without :latest
            if name.endswith(":latest"):
                names.append(name[: -len(":latest")])
    return names


def _ollama_list_cli() -> list[str]:
    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    names = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            names.append(parts[0])
    return names


def _write_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def set_active_model(model_id: str, *, unload_previous: bool = True) -> dict[str, Any]:
    """Switch active chat model in config.yaml. Does not download."""
    model_id = (model_id or "").strip()
    if not model_id:
        raise ValueError("model id required")
    catalog = {m["id"]: m for m in _merge_catalog(load_config())}
    entry = catalog.get(model_id) or get_model_entry(model_id)
    ollama_name = entry.get("ollama_name") or entry["id"]

    with _CFG_LOCK:
        cfg = load_config()
        prev = ((cfg.get("llm") or {}).get("model") or "").strip()
        if unload_previous and prev and prev != ollama_name and prev != model_id:
            unload_model(prev)
        llm = dict(cfg.get("llm") or {})
        llm["provider"] = llm.get("provider") or "ollama"
        llm["model"] = ollama_name
        llm["path"] = f"ollama://{ollama_name}"
        llm["base_url"] = llm.get("base_url") or "http://localhost:11434"
        # Mirror active entry knobs at top level for older readers.
        for key in ("num_ctx", "num_predict", "temperature", "keep_alive"):
            if entry.get(key) is not None:
                llm[key] = entry[key]
        # Ensure models list exists for future edits.
        if not isinstance(llm.get("models"), list) or not llm["models"]:
            llm["models"] = deepcopy(DEFAULT_MODELS)
        cfg["llm"] = llm
        _write_config(cfg)

    return {
        "ok": True,
        "model": ollama_name,
        "model_id": entry["id"],
        "label": entry.get("label") or entry["id"],
        "installed": ollama_name in set(ollama_installed_names()),
        "notes": entry.get("notes") or "",
    }


def pull_model(model_id: str) -> dict[str, Any]:
    """Download via Ollama only (`ollama pull`). Runs synchronously; use thread from API."""
    entry = get_model_entry(model_id)
    name = entry.get("ollama_name") or entry["id"]
    with _PULL_LOCK:
        if _pull_status.get("running"):
            raise RuntimeError(f"Already pulling {_pull_status.get('model')}")
        _pull_status.update({"running": True, "model": name, "log": "", "ok": None})
    try:
        proc = subprocess.run(
            ["ollama", "pull", name],
            capture_output=True,
            text=True,
            timeout=None,
            check=False,
        )
        log = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        ok = proc.returncode == 0
        with _PULL_LOCK:
            _pull_status.update({"running": False, "model": name, "log": log[-4000:], "ok": ok})
        if not ok:
            raise OllamaError(f"ollama pull {name} failed (exit {proc.returncode}): {log[-500:]}")
        return {"ok": True, "model": name, "log": log[-2000:]}
    except FileNotFoundError as exc:
        with _PULL_LOCK:
            _pull_status.update({"running": False, "ok": False, "log": "ollama not on PATH"})
        raise OllamaError("Ollama not found on PATH") from exc
    except Exception:
        with _PULL_LOCK:
            _pull_status["running"] = False
            _pull_status["ok"] = False
        raise


def pull_status() -> dict[str, Any]:
    with _PULL_LOCK:
        return dict(_pull_status)


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    num_predict: int | None = None,
    extra_options: dict | None = None,
) -> str:
    text = []
    for piece in chat_stream(
        messages,
        temperature=temperature,
        num_predict=num_predict,
        extra_options=extra_options,
    ):
        text.append(piece)
    return "".join(text)


def chat_stream(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    num_predict: int | None = None,
    extra_options: dict | None = None,
    should_stop=None,
) -> Iterator[str]:
    s = llm_settings()
    options = {
        "temperature": s["temperature"] if temperature is None else temperature,
        "num_ctx": min(int(s["num_ctx"]), 8192),
        "num_predict": s["num_predict"] if num_predict is None else num_predict,
        "num_thread": s["num_thread"],
        "num_batch": s["num_batch"],
    }
    if s.get("num_gpu") is not None:
        options["num_gpu"] = s["num_gpu"]
    for key, val in (extra_options or {}).items():
        if val is None or val == "" or val == []:
            continue
        options[key] = val
    payload = {
        "model": s["model"],
        "messages": messages,
        "stream": True,
        "keep_alive": s["keep_alive"],
        "options": options,
    }
    url = s["base_url"].rstrip("/") + "/api/chat"
    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
            with client.stream("POST", url, json=payload) as resp:
                if resp.status_code >= 400:
                    body = resp.read().decode("utf-8", errors="replace")
                    raise OllamaError(f"Ollama HTTP {resp.status_code}: {body[:300]}")
                for line in resp.iter_lines():
                    if should_stop and should_stop():
                        break
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise OllamaError(str(data["error"]))
                    piece = (data.get("message") or {}).get("content") or ""
                    if piece:
                        yield piece
                    if data.get("done"):
                        break
    except httpx.ConnectError as exc:
        raise OllamaError(
            "Cannot reach Ollama. Start it, then retry. Expected at "
            f"{s['base_url']}"
        ) from exc


def unload_model(model: str | None = None) -> None:
    """Drop a chat model from VRAM. Safe if Ollama is already down."""
    s = llm_settings()
    name = model or s["model"]
    url = s["base_url"].rstrip("/") + "/api/generate"
    try:
        httpx.post(
            url,
            json={"model": name, "prompt": "", "keep_alive": 0},
            timeout=8.0,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["ollama", "stop", name],
            check=False,
            timeout=20,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
