"""Standalone interactive launcher for EduRAG Server appliance.
Handles hardware probe, custom model storage path, Ollama auto-install/start,
intelligent model recommendation, live progress download, zero-bat DB init,
LAN connection display, and safe VRAM unload on shutdown.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

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

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.auth import jwt_secret
from app.config_load import ROOT, load_config
from app.db import init_db
from app.llm import get_model_entry, set_active_model, unload_model
from app.model_downloader import (
    apply_models_dir,
    get_default_models_dir,
    get_drive_free_space_gb,
    install_and_await_ollama,
    is_model_installed,
    pull_model_with_progress,
)
from app.server import local_ip
from app.shutdown import ensure_ollama, ollama_reachable, stop_local
from app.system_info import collect

console = Console()

MODEL_PRESETS = [
    {
        "id": "qwen2.5:7b-instruct",
        "name": "Qwen 2.5 7B Instruct",
        "desc": "Best Quality & Reasoning. Highly recommended for GPUs with >=8-12 GB VRAM.",
        "size_gb": 4.7,
        "min_vram": 8.0,
        "min_ram": 16.0,
    },
    {
        "id": "qwen2.5:3b-instruct",
        "name": "Qwen 2.5 3B Instruct",
        "desc": "Ultra Fast & Lightweight (~2.0 GB VRAM). Best for 6 GB GPUs or CPU + multiple LAN users.",
        "size_gb": 1.9,
        "min_vram": 4.0,
        "min_ram": 8.0,
    },
    {
        "id": "qwen2.5:1.5b-instruct",
        "name": "Qwen 2.5 1.5B Instruct",
        "desc": "Minimal Footprint (~1.0 GB). Ideal for budget laptops, 4 GB GPUs, or pure CPU servers.",
        "size_gb": 1.0,
        "min_vram": 2.0,
        "min_ram": 4.0,
    },
]


def print_banner() -> None:
    banner_text = (
        "[bold cyan]EduRAG On-Premise Learning Appliance[/bold cyan]\n"
        "[white]High-Performance Local RAG Server for Schools & Colleges[/white]\n"
        "[dim]Zero Cloud Dependencies • Strict LAN Privacy • Port 4747[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def display_system_specs(info: dict) -> None:
    table = Table(title="Host System Hardware Assessment", border_style="blue")
    table.add_column("Component", style="cyan bold", width=18)
    table.add_column("Detected Specification", style="white")

    table.add_row("Operating System", str(info.get("os")))
    cpu = info.get("cpu", {})
    cores = cpu.get("cores", "?")
    threads = cpu.get("threads", cpu.get("logical_cpus", "?"))
    table.add_row("CPU Processor", f"{cpu.get('name')} ({cores} Cores / {threads} Threads)")
    table.add_row("System RAM", f"{info.get('ram_gb', '?')} GB")

    gpu = info.get("gpu", {})
    if gpu.get("found"):
        cuda_info = f", CUDA {gpu['cuda']}" if gpu.get("cuda") else ""
        table.add_row(
            "NVIDIA GPU",
            f"[bold green]{gpu['name']}[/bold green] ({info.get('vram_gb')} GB VRAM{cuda_info})",
        )
    else:
        table.add_row("Graphics (GPU)", "[yellow]No Dedicated NVIDIA GPU detected (CPU Mode)[/yellow]")

    console.print(table)


def recommend_model(info: dict) -> dict:
    vram = info.get("vram_gb") or 0.0
    ram = info.get("ram_gb") or 8.0

    if vram >= 8.5:
        return MODEL_PRESETS[0]  # 7B
    elif vram >= 5.0 or ram >= 24.0:
        return MODEL_PRESETS[1]  # 3B (Fastest for multi-client concurrency on 6GB cards)
    else:
        return MODEL_PRESETS[2]  # 1.5B


def setup_model_storage_path(interactive: bool = True) -> Path:
    current_dir = get_default_models_dir()
    free_gb = get_drive_free_space_gb(current_dir)

    console.print("\n[bold cyan]Model Storage Location:[/bold cyan]")
    console.print(f"Current Path: [bold white]{current_dir}[/bold white]")
    drive_color = "green" if free_gb >= 20.0 else "yellow" if free_gb >= 10.0 else "red"
    console.print(f"Free Disk Space: [{drive_color}]{free_gb} GB free[/{drive_color}]")

    cfg = load_config()
    configured_custom = (cfg.get("llm") or {}).get("models_dir")
    if configured_custom or not interactive:
        if configured_custom:
            apply_models_dir(Path(configured_custom))
        return current_dir

    if free_gb < 15.0:
        console.print(
            "[bold yellow]Warning: Available space on this drive is below 15 GB.[/bold yellow]"
        )

    console.print("[dim]Press Enter to keep this location, or type 'change' to specify a custom folder (e.g. D:\\OllamaModels):[/dim]")
    try:
        choice = input("Choice [Enter to keep / 'change']: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if choice in ("change", "c", "custom"):
        try:
            custom_input = input("Enter custom folder path (e.g. D:\\OllamaModels): ").strip()
        except (EOFError, KeyboardInterrupt):
            custom_input = ""
        if custom_input:
            custom_path = Path(custom_input).resolve()
            custom_free = get_drive_free_space_gb(custom_path)
            console.print(
                f"[green]Configuring model storage to:[/green] {custom_path} "
                f"({custom_free} GB free)"
            )
            apply_models_dir(custom_path)
            return custom_path

    apply_models_dir(current_dir)
    return current_dir


def verify_and_start_ollama(interactive: bool = True) -> bool:
    console.print("\n[bold cyan]Ollama Runtime Status:[/bold cyan]")
    if ollama_reachable():
        console.print("[bold green][OK] Ollama is online and responding on port 11434.[/bold green]")
        return True

    res = ensure_ollama(wait_seconds=6)
    if res.get("ready"):
        console.print("[bold green][OK] Ollama background service started successfully.[/bold green]")
        return True

    console.print("[yellow]! Ollama is not currently installed or running.[/yellow]")
    if interactive:
        console.print(
            "[bold white]EduRAG can automatically download and launch the official Windows Ollama installer.[/bold white]"
        )
        try:
            ans = input("Download and install Ollama now? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans in ("", "y", "yes"):
            ok = install_and_await_ollama()
            if ok:
                return True

    console.print(
        Panel.fit(
            "[bold red]Ollama is required for the LLM chat engine.[/bold red]\n"
            "Please install Ollama from [underline cyan]https://ollama.com/download/windows[/underline cyan]\n"
            "After installation completes, re-run this launcher.",
            title="[bold yellow]Ollama Required[/bold yellow]",
        )
    )
    return False


def select_and_pull_model(info: dict, interactive: bool = True) -> str:
    rec = recommend_model(info)
    cfg = load_config()
    existing_model = (cfg.get("llm") or {}).get("model") or rec["id"]

    console.print("\n[bold cyan]AI Language Model Selection:[/bold cyan]")
    console.print(
        f"Hardware Recommendation: [bold green]{rec['name']}[/bold green] "
        f"([dim]{rec['desc']}[/dim])"
    )

    chosen_model = existing_model
    if interactive:
        console.print("\nAvailable Pre-configured Models:")
        for idx, preset in enumerate(MODEL_PRESETS, start=1):
            is_rec = " [bold green](Recommended for your PC)[/bold green]" if preset["id"] == rec["id"] else ""
            is_active = " [dim][Current Config][/dim]" if preset["id"] == existing_model else ""
            console.print(
                f"  [{idx}] [bold white]{preset['name']}[/bold white] ({preset['id']}){is_rec}{is_active}\n"
                f"      [dim]{preset['desc']} (~{preset['size_gb']} GB download)[/dim]"
            )
        console.print("  [4] Custom model tag (specify any custom Ollama model name)")

        try:
            choice = input(f"\nSelect model [1-4] or press Enter for '{existing_model}': ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""

        if choice == "1":
            chosen_model = MODEL_PRESETS[0]["id"]
        elif choice == "2":
            chosen_model = MODEL_PRESETS[1]["id"]
        elif choice == "3":
            chosen_model = MODEL_PRESETS[2]["id"]
        elif choice == "4":
            try:
                custom_name = input("Enter custom Ollama model tag: ").strip()
                if custom_name:
                    chosen_model = custom_name
            except (EOFError, KeyboardInterrupt):
                pass

    # Check if model is already downloaded in Ollama
    if is_model_installed(chosen_model):
        console.print(f"[bold green][OK] Model '{chosen_model}' is already on disk and ready.[/bold green]")
    else:
        console.print(f"[bold yellow]Model '{chosen_model}' not found in local library. Initiating download...[/bold yellow]")
        success = pull_model_with_progress(chosen_model)
        if not success:
            console.print(f"[bold red]Failed to download {chosen_model}. Please verify your internet connection.[/bold red]")
            sys.exit(1)

    # Set as active model in configuration
    try:
        set_active_model(chosen_model, unload_previous=True)
    except Exception as exc:
        console.print(f"[dim]Note: Active model recorded: {chosen_model}[/dim]")

    return chosen_model


def initialize_appliance() -> None:
    """Zero-bat database initialization & demo account seeding."""
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "uploads").mkdir(parents=True, exist_ok=True)

    jwt_secret()
    store_conn = init_db()

    from app.bootstrap import seed_demo_users
    from app.db.store import Store

    store = Store(store_conn)
    seed_demo_users(store)
    console.print("[bold green][OK] Database & demo accounts initialized successfully.[/bold green]")


def run_server(host: str = "0.0.0.0", port: int = 4747) -> None:
    import uvicorn

    server_ip = local_ip()

    lan_panel = (
        f"[bold white]Local Server PC Access:[/bold white]      [bold cyan]http://127.0.0.1:{port}[/bold cyan]\n"
        f"[bold white]Connected Client PCs (LAN):[/bold white]  [bold green]http://{server_ip}:{port}[/bold green]\n\n"
        "[bold yellow]How the 5 Client PCs Connect:[/bold yellow]\n"
        "  1. Ensure the other 5 PCs are on the same Wi-Fi / LAN router.\n"
        f"  2. On each PC, open a web browser (Chrome, Edge, Firefox) and visit:\n"
        f"     [bold underline green]http://{server_ip}:{port}[/bold underline green]\n"
        "  3. Sign in using any demo account:\n"
        "     - [bold cyan]Teacher:[/bold cyan] teacher@edurag.local  /  teacher123\n"
        "     - [bold cyan]Student:[/bold cyan] student@edurag.local  /  student123\n"
        "     - [bold cyan]Admin:[/bold cyan]   admin@edurag.local    /  admin123\n\n"
        "[dim]Note: If client PCs cannot connect, ensure Windows Defender Firewall allows\n"
        f"inbound TCP port {port} on the Private network profile.[/dim]\n\n"
        "[bold red]Press Ctrl+C at any time to safely stop the server and release GPU memory.[/bold red]"
    )

    console.print(Panel(lan_panel, title="[bold green]EduRAG SERVER IS LIVE[/bold green]", border_style="green"))

    def signal_handler(_sig, _frame):
        console.print("\n[bold yellow]Gracefully stopping EduRAG and unloading LLM from GPU VRAM...[/bold yellow]")
        try:
            unload_model()
            stop_local()
        except Exception:
            pass
        console.print("[bold green]EduRAG stopped. GPU VRAM released. Goodbye![/bold green]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    uvicorn.run("app.server:app", host=host, port=port, log_level="info")


def main() -> int:
    parser = argparse.ArgumentParser(description="EduRAG Server Standalone Launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4747, help="Port to bind (default: 4747)")
    parser.add_argument("--model", default=None, help="Force specific model ID")
    parser.add_argument("--non-interactive", action="store_true", help="Run without prompts")
    parser.add_argument("--check", action="store_true", help="Run hardware check and exit")
    args = parser.parse_args()

    print_banner()

    # Step 1: Probe Hardware
    info = collect()
    display_system_specs(info)

    if args.check:
        return 0

    interactive = not args.non_interactive

    # Step 2: Model Storage Path
    setup_model_storage_path(interactive=interactive)

    # Step 3: Ollama Runtime
    if not verify_and_start_ollama(interactive=interactive):
        return 1

    # Step 4: Model Selection & Download
    if args.model:
        if not is_model_installed(args.model):
            pull_model_with_progress(args.model)
        set_active_model(args.model)
    else:
        select_and_pull_model(info, interactive=interactive)

    # Step 5: Appliance DB & Account Init
    initialize_appliance()

    # Step 6: Start Web & API Server
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
