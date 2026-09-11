"""Start/stop helpers for EduRAG + local Ollama (port 11434)."""
from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.config_load import ROOT, load_config
from app.llm import llm_settings, unload_model

OLLAMA_PORT = 11434
MARKER = ROOT / "data" / ".edurag_started_ollama"


def resolve_ollama_exe() -> str | None:
    """Find ollama.exe even when PATH is thin (double-clicked .bat)."""
    import shutil

    found = shutil.which("ollama")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Ollama" / "ollama.exe",
        Path(r"C:\Program Files\Ollama\ollama.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
    ]
    for path in candidates:
        if path.is_file():
            os.environ["PATH"] = str(path.parent) + os.pathsep + os.environ.get("PATH", "")
            return str(path)
    return None


def listening_pids(port: int) -> list[int]:
    pids: list[int] = []
    try:
        raw = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return pids
    needle = f":{port}"
    for line in raw.splitlines():
        if "LISTENING" not in line.upper() or needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pids.append(int(parts[-1]))
        except ValueError:
            continue
    return sorted(set(pids))


def ollama_reachable(timeout: float = 1.5) -> bool:
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{OLLAMA_PORT}/api/tags",
            timeout=timeout,
        )
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _write_started_marker(pid: int) -> None:
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(f"{pid}\n", encoding="utf-8")


def clear_started_marker() -> None:
    try:
        MARKER.unlink(missing_ok=True)
    except OSError:
        pass


def owned_ollama_pid() -> int | None:
    """PID of ollama serve that EduRAG launched, if still recorded."""
    if not MARKER.is_file():
        return None
    try:
        return int(MARKER.read_text(encoding="utf-8").strip().splitlines()[0])
    except (OSError, ValueError, IndexError):
        return None


def we_started_ollama() -> bool:
    owned = owned_ollama_pid()
    if owned is None:
        return False
    return owned in set(listening_pids(OLLAMA_PORT))


def established_client_pids(port: int) -> list[int]:
    """PIDs with ESTABLISHED TCP involving :port, excluding the LISTENING server PID."""
    listeners = set(listening_pids(port))
    clients: set[int] = set()
    try:
        raw = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    needle = f":{port}"
    for line in raw.splitlines():
        upper = line.upper()
        if "ESTABLISHED" not in upper or needle not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid in listeners or pid <= 0:
            continue
        clients.add(pid)
    return sorted(clients)


def _launch_ollama_serve() -> None:
    exe = resolve_ollama_exe() or "ollama"
    cfg = load_config()
    models_dir = os.environ.get("OLLAMA_MODELS") or (cfg.get("llm") or {}).get("models_dir")
    env_models = f'set OLLAMA_MODELS={models_dir}&& ' if models_dir else ''
    env_prefix = (
        f"{env_models}"
        "set OLLAMA_MAX_LOADED_MODELS=1&& "
        "set OLLAMA_NUM_PARALLEL=1&& "
        "set OLLAMA_KEEP_ALIVE=5m&& "
        "set OLLAMA_FLASH_ATTENTION=1&& "
    )
    quoted = f'"{exe}"' if " " in exe else exe
    subprocess.Popen(
        f'start "Ollama" /MIN cmd /c "{env_prefix}{quoted} serve"',
        shell=True,
        cwd=str(ROOT),
    )


def ensure_ollama(*, wait_seconds: int = 25) -> dict:
    """If Ollama is already up, leave it. Otherwise start it and remember its PID."""
    if ollama_reachable():
        owned = owned_ollama_pid()
        if owned is not None and owned not in set(listening_pids(OLLAMA_PORT)):
            clear_started_marker()
        return {
            "ready": True,
            "started_by_us": we_started_ollama(),
            "message": f"Ollama already answering on {OLLAMA_PORT}",
        }
    exe = resolve_ollama_exe()
    if not exe:
        clear_started_marker()
        return {
            "ready": False,
            "started_by_us": False,
            "message": (
                "Ollama executable not found on PATH or in "
                "%LOCALAPPDATA%\\Programs\\Ollama. "
                "Install from https://ollama.com/download or open a new terminal after install."
            ),
        }
    clear_started_marker()
    _launch_ollama_serve()
    for _ in range(max(1, wait_seconds)):
        if ollama_reachable():
            pids = listening_pids(OLLAMA_PORT)
            if pids:
                _write_started_marker(pids[0])
            return {
                "ready": True,
                "started_by_us": True,
                "message": f"Ollama started ({exe}) and ready on {OLLAMA_PORT}",
            }
        time.sleep(1)
    return {
        "ready": False,
        "started_by_us": False,
        "message": (
            f"Started Ollama ({exe}) but it did not answer on {OLLAMA_PORT} yet. "
            "EduRAG will still start."
        ),
    }


def stop_ollama_model() -> None:
    unload_model()
    model = llm_settings()["model"]
    exe = resolve_ollama_exe() or "ollama"
    try:
        subprocess.run(
            [exe, "stop", model],
            check=False,
            timeout=20,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _kill_pids(pids: list[int]) -> list[int]:
    killed: list[int] = []
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=False,
                capture_output=True,
                timeout=10,
            )
            killed.append(pid)
        except (OSError, subprocess.TimeoutExpired):
            continue
    return killed


def stop_ollama_process() -> list[int]:
    """Force-stop listeners on 11434 (ollama serve)."""
    return _kill_pids(listening_pids(OLLAMA_PORT))


def stop_local() -> dict:
    """
    Always free EduRAG port (4747).
    Unload VRAM + stop Ollama only when nothing else is using port 11434.
    If EduRAG did not start Ollama, never kill the Ollama process.
    """
    cfg = load_config()
    port = int((cfg.get("server") or {}).get("port") or 4747)
    edurag_pids = listening_pids(port)
    killed_edurag = _kill_pids(edurag_pids)

    time.sleep(0.6)
    other_clients = established_client_pids(OLLAMA_PORT)
    owned = owned_ollama_pid()
    listeners = set(listening_pids(OLLAMA_PORT))
    we_own = owned is not None and owned in listeners
    unloaded = False
    killed_ollama: list[int] = []
    ollama_note = ""

    if other_clients:
        ollama_note = (
            f"Ollama kept (other apps still connected on {OLLAMA_PORT}: "
            f"pids {other_clients}). Model left loaded."
        )
    else:
        stop_ollama_model()
        unloaded = True
        if we_own:
            killed_ollama = _kill_pids([owned])
            clear_started_marker()
            ollama_note = (
                f"Ollama stopped (EduRAG had started pid {owned}; "
                f"nothing else on {OLLAMA_PORT})."
            )
        else:
            if owned is not None and owned not in listeners:
                clear_started_marker()
            ollama_note = (
                f"Chat model unloaded. Ollama process kept "
                f"(already running before EduRAG, or started by another app)."
            )

    return {
        "port": port,
        "killed": killed_edurag,
        "unloaded": unloaded,
        "killed_ollama": killed_ollama,
        "kept_ollama_for_clients": other_clients,
        "ollama_note": ollama_note,
    }
