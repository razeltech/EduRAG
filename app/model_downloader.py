"""Ollama setup assistant & live streaming model puller with rich progress bar."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from app.config_load import ROOT, load_config
from app.shutdown import OLLAMA_PORT, ollama_reachable, resolve_ollama_exe

console = Console()

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"


def get_default_models_dir() -> Path:
    """Default directory where Ollama stores model weights on Windows."""
    env = os.environ.get("OLLAMA_MODELS")
    if env:
        return Path(env).resolve()
    cfg = load_config()
    cfg_path = (cfg.get("llm") or {}).get("models_dir")
    if cfg_path:
        return Path(cfg_path).resolve()
    return Path.home() / ".ollama" / "models"


def get_drive_free_space_gb(path: Path) -> float:
    """Return free disk space in GB on the drive holding path."""
    try:
        resolved = path.resolve()
        # Find existing parent if path does not yet exist
        target = resolved
        while not target.exists() and target.parent != target:
            target = target.parent
        usage = shutil.disk_usage(target)
        return round(usage.free / (1024**3), 1)
    except Exception:
        return 0.0


def apply_models_dir(custom_path: Path) -> None:
    """Set OLLAMA_MODELS env var and record in config.yaml."""
    custom_path.mkdir(parents=True, exist_ok=True)
    os.environ["OLLAMA_MODELS"] = str(custom_path)
    from app.llm import _write_config

    cfg = load_config()
    llm = dict(cfg.get("llm") or {})
    llm["models_dir"] = str(custom_path)
    cfg["llm"] = llm
    _write_config(cfg)


def download_ollama_installer(dest_dir: Path | None = None) -> Path:
    """Download official Windows OllamaSetup.exe with live progress bar."""
    target_dir = dest_dir or ROOT / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    installer_path = target_dir / "OllamaSetup.exe"

    if installer_path.is_file() and installer_path.stat().st_size > 20_000_000:
        console.print(
            f"[bold green][OK] Found existing installer at:[/bold green] {installer_path}"
        )
        return installer_path

    console.print(
        f"[bold cyan]Downloading official Ollama Windows installer...[/bold cyan]"
    )

    with httpx.stream(
        "GET", OLLAMA_INSTALLER_URL, follow_redirects=True, timeout=120.0
    ) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("OllamaSetup.exe", total=total or None)
            with open(installer_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1024 * 64):
                    f.write(chunk)
                    if total:
                        progress.update(task, advance=len(chunk))

    console.print(f"[bold green][OK] Downloaded Ollama installer to:[/bold green] {installer_path}")
    return installer_path


def install_and_await_ollama(timeout_seconds: int = 180) -> bool:
    """Run OllamaSetup.exe and wait until Ollama is installed and answering."""
    if ollama_reachable():
        return True

    installer = download_ollama_installer()
    console.print("\n[bold yellow]Launching Ollama Setup...[/bold yellow]")
    console.print(
        Panel.fit(
            "[white]Please follow the Windows installer prompts to finish installing Ollama.\n"
            "This window will automatically detect completion and continue.[/white]",
            title="[bold cyan]Ollama Installation in Progress[/bold cyan]",
            border_style="cyan",
        )
    )

    try:
        subprocess.Popen([str(installer)])
    except Exception as exc:
        console.print(f"[bold red]Failed to start installer:[/bold red] {exc}")
        return False

    with console.status("[bold green]Waiting for Ollama to finish installing...", spinner="dots"):
        start = time.time()
        while time.time() - start < timeout_seconds:
            time.sleep(3)
            # Check if ollama.exe has appeared
            exe = resolve_ollama_exe()
            if exe:
                # Attempt to ensure it is running
                from app.shutdown import ensure_ollama

                res = ensure_ollama(wait_seconds=5)
                if res.get("ready"):
                    console.print("[bold green][OK] Ollama is now installed and running![/bold green]\n")
                    return True

    console.print("[bold red]Timeout waiting for Ollama installer.[/bold red]")
    return False


def is_model_installed(model_name: str, base_url: str = "http://localhost:11434") -> bool:
    """Check if model is present in Ollama's local tags."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
        if r.status_code == 200:
            models = r.json().get("models") or []
            installed = {m.get("name") for m in models if m.get("name")}
            clean_name = model_name.split(":")[0] if ":" in model_name else model_name
            # Check exact match or base tag match
            for tag in installed:
                if tag == model_name or tag.startswith(f"{clean_name}:") or tag == clean_name:
                    return True
    except Exception:
        pass
    return False


def pull_model_with_progress(
    model_name: str, base_url: str = "http://localhost:11434"
) -> bool:
    """Stream Ollama pull with real-time progress bar (MB, GB, %, speed)."""
    url = f"{base_url.rstrip('/')}/api/pull"
    payload = {"name": model_name, "stream": True}

    console.print(f"\n[bold cyan]Downloading model:[/bold cyan] [bold white]{model_name}[/bold white]")
    console.print(
        "[dim]Weights are downloaded directly from the Ollama library. Please do not close this window.[/dim]\n"
    )

    current_layer_id: str | None = None
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Pulling {model_name}...", total=None)

        try:
            with httpx.Client(timeout=httpx.Timeout(3600.0, connect=10.0)) as client:
                with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code >= 400:
                        body = resp.read().decode("utf-8", errors="replace")
                        console.print(
                            f"[bold red]Failed to pull model ({resp.status_code}):[/bold red] {body[:200]}"
                        )
                        return False

                    for line in resp.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue

                        status = data.get("status") or ""
                        total = data.get("total")
                        completed = data.get("completed", 0)
                        digest = data.get("digest")

                        if data.get("error"):
                            console.print(f"[bold red]Error from Ollama:[/bold red] {data['error']}")
                            return False

                        if digest and digest != current_layer_id:
                            current_layer_id = digest
                            short_id = digest[:12] if len(digest) > 12 else digest
                            progress.update(
                                task,
                                description=f"Layer {short_id} ({status})",
                                total=total,
                                completed=completed,
                            )
                        elif total and total > 0:
                            progress.update(
                                task,
                                description=f"{model_name} ({status})",
                                total=total,
                                completed=completed,
                            )
                        else:
                            progress.update(
                                task,
                                description=f"{model_name}: {status}",
                            )

                        if status == "success":
                            progress.update(
                                task,
                                description=f"[bold green]{model_name} Ready[/bold green]",
                                completed=total or 100,
                                total=total or 100,
                            )
                            break
        except httpx.ConnectError:
            console.print("[bold red]Cannot connect to Ollama at[/bold red] " f"{base_url}")
            return False
        except Exception as exc:
            console.print(f"[bold red]Error during model download:[/bold red] {exc}")
            return False

    console.print(f"[bold green][OK] Successfully downloaded and verified {model_name}![/bold green]\n")
    return True
