"""Hardware probe for Phase 0. No model loading — just what the box can run."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=12, check=False
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _ram_gb() -> float | None:
    if os.name == "nt":
        out = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
            ]
        )
        if out and out.isdigit():
            return round(int(out) / (1024**3), 1)
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        return None


def _cpu() -> dict[str, Any]:
    info: dict[str, Any] = {
        "name": platform.processor() or "unknown",
        "machine": platform.machine(),
    }
    if os.name == "nt":
        name = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).Name",
            ]
        )
        cores = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).NumberOfCores",
            ]
        )
        threads = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors",
            ]
        )
        if name:
            info["name"] = name
        if cores and cores.isdigit():
            info["cores"] = int(cores)
        if threads and threads.isdigit():
            info["threads"] = int(threads)
    info["logical_cpus"] = os.cpu_count()
    return info


def _gpu() -> dict[str, Any]:
    csv = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,cuda_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not csv:
        # Older nvidia-smi builds don't expose cuda_version in query-gpu.
        csv = _run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ]
        )
        if not csv:
            return {"found": False}
        parts = [p.strip() for p in csv.split(",")]
        name, vram, driver = (parts + ["", "", ""])[:3]
        return {
            "found": True,
            "name": name,
            "vram_mib": int(vram) if vram.isdigit() else vram,
            "driver": driver,
        }
    parts = [p.strip() for p in csv.split(",")]
    name, vram, driver = (parts + ["", "", ""])[:3]
    cuda = parts[3] if len(parts) > 3 else None
    payload: dict[str, Any] = {
        "found": True,
        "name": name,
        "vram_mib": int(vram) if str(vram).isdigit() else vram,
        "driver": driver,
    }
    if cuda:
        payload["cuda"] = cuda
    return payload


def _ollama() -> dict[str, Any]:
    exe = shutil.which("ollama")
    listing = _run(["ollama", "list"]) if exe else None
    models: list[str] = []
    if listing:
        for line in listing.splitlines()[1:]:
            name = line.split()[0] if line.strip() else ""
            if name:
                models.append(name)
    return {"installed": bool(exe), "path": exe, "models": models}


def collect() -> dict[str, Any]:
    gpu = _gpu()
    vram_mib = gpu.get("vram_mib") if gpu.get("found") else None
    vram_gb = round(int(vram_mib) / 1024, 1) if isinstance(vram_mib, int) else None
    return {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu": _cpu(),
        "ram_gb": _ram_gb(),
        "gpu": gpu,
        "vram_gb": vram_gb,
        "ollama": _ollama(),
        "project_root": str(Path(__file__).resolve().parent.parent),
    }


def format_report(info: dict[str, Any]) -> str:
    gpu = info["gpu"]
    cpu = info["cpu"]
    lines = [
        "SYSTEM INFO",
        "============",
        f"OS:         {info['os']}",
        f"Python:     {info['python']}",
        f"CPU:        {cpu.get('name')}  "
        f"({cpu.get('cores', '?')}C/{cpu.get('threads', cpu.get('logical_cpus', '?'))}T)",
        f"RAM:        {info.get('ram_gb', '?')} GB",
    ]
    if gpu.get("found"):
        vram = info.get("vram_gb")
        extra = f", CUDA {gpu['cuda']}" if gpu.get("cuda") else ""
        lines.append(
            f"GPU:        {gpu['name']}  ({vram} GB VRAM, driver {gpu.get('driver')}{extra})"
        )
    else:
        lines.append("GPU:        [NOT FOUND]  nvidia-smi unavailable")
    ollama = info["ollama"]
    if ollama["installed"]:
        models = ", ".join(ollama["models"]) or "(none pulled)"
        lines.append(f"Ollama:     [FOUND] {models}")
    else:
        lines.append("Ollama:     [MISSING]")
    lines.append("")
    if isinstance(info.get("vram_gb"), float) and info["vram_gb"] <= 12.5:
        lines.append(
            "VRAM budget (12 GB card): LLM ~6-8 GB, embedding ~1 GB, "
            "reranker ~1 GB. Prefer a Q4/Q5 7B-9B instruct model."
        )
    return "\n".join(lines)
