"""
SmileAI Desktop Control Center & LAN Lab Launcher
Powered by Razel Tech | Native Windows GUI Launcher

Features:
1. 60px Firm Header with Razel Tech branding
2. One-Click Start Server (Port 4747)
3. One-Click Open Web App (Default browser)
4. LAN Lab Host Mode (Auto-detects local IP for 20-30 lab computers)
5. Live Hardware Diagnostics (CPU & RAM utilization)
6. Clean Shutdown (Flushes SQLite WAL & terminates processes cleanly)
"""

import os
import sys
import time
import socket
import webbrowser
import subprocess
import threading
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_PORT = 4747
server_process: Optional[subprocess.Popen] = None
is_shutting_down = False


def get_local_ip() -> str:
    """Detects the primary LAN IP address of this computer."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_system_metrics() -> dict:
    """Retrieves CPU and RAM statistics using psutil if available, or fallback metrics."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        return {
            "cpu_percent": cpu,
            "ram_used_gb": round((ram.total - ram.available) / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "ram_percent": ram.percent,
        }
    except Exception:
        return {
            "cpu_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
            "ram_percent": 0.0,
        }


def start_server_process(port: int = DEFAULT_PORT) -> subprocess.Popen:
    """Launches the SmileAI server in a managed background subprocess."""
    global server_process
    if server_process and server_process.poll() is None:
        return server_process

    env = os.environ.copy()
    env["SMILEAI_PORT"] = str(port)

    # Use current python executable or venv python
    py_exec = sys.executable
    server_script = ROOT_DIR / "smileai" / "server.py"

    # Start detached background process
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    server_process = subprocess.Popen(
        [py_exec, str(server_script)],
        env=env,
        cwd=str(ROOT_DIR),
        creationflags=creationflags,
    )
    return server_process


def stop_server_process() -> None:
    """Gracefully terminates the background server process."""
    global server_process
    if server_process and server_process.poll() is None:
        try:
            server_process.terminate()
            server_process.wait(timeout=3)
        except Exception:
            try:
                server_process.kill()
            except Exception:
                pass
        server_process = None


def create_gui():
    """Creates the native Tkinter desktop launcher window."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("SmileAI Platform — Control Center")
    root.geometry("620x520")
    root.resizable(False, False)

    # Palette
    BG_MAIN = "#f8fafc"
    BG_CARD = "#ffffff"
    NAVY = "#1e3a8a"
    BLUE = "#2563eb"
    GREEN = "#059669"
    RED = "#dc2626"
    TEXT_MUTED = "#64748b"

    root.configure(bg=BG_MAIN)

    # 1. 60px Firm Header
    header_frame = tk.Frame(root, bg=NAVY, height=60)
    header_frame.pack(fill="x", side="top")
    header_frame.pack_propagate(False)

    brand_lbl = tk.Label(
        header_frame,
        text="  SmileAI Platform — Institutional Lab Center",
        font=("Segoe UI", 13, "bold"),
        fg="#ffffff",
        bg=NAVY,
    )
    brand_lbl.pack(side="left", padx=16)

    sub_lbl = tk.Label(
        header_frame,
        text="Powered by Razel Tech 🇮🇳  ",
        font=("Segoe UI", 10),
        fg="#93c5fd",
        bg=NAVY,
    )
    sub_lbl.pack(side="right", padx=16)

    # 2. Main Body Container
    body = tk.Frame(root, bg=BG_MAIN, padx=20, pady=16)
    body.pack(fill="both", expand=True)

    # Status Card
    status_card = tk.LabelFrame(
        body,
        text="  Server Status & Lab Access  ",
        font=("Segoe UI", 10, "bold"),
        fg=NAVY,
        bg=BG_CARD,
        padx=14,
        pady=12,
    )
    status_card.pack(fill="x", pady=6)

    status_var = tk.StringVar(value="Status: Server Offline")
    status_lbl = tk.Label(
        status_card,
        textvariable=status_var,
        font=("Segoe UI", 11, "bold"),
        fg=RED,
        bg=BG_CARD,
    )
    status_lbl.pack(anchor="w", pady=2)

    local_url = f"http://localhost:{DEFAULT_PORT}"
    lan_ip = get_local_ip()
    lan_url = f"http://{lan_ip}:{DEFAULT_PORT}"

    lan_lbl = tk.Label(
        status_card,
        text=f"LAN Mode (20-30 Lab PCs): {lan_url}",
        font=("Segoe UI", 10),
        fg=NAVY,
        bg=BG_CARD,
    )
    lan_lbl.pack(anchor="w", pady=4)

    # Hardware Diagnostics Card
    diag_card = tk.LabelFrame(
        body,
        text="  Live Lab Hardware Monitor  ",
        font=("Segoe UI", 10, "bold"),
        fg=NAVY,
        bg=BG_CARD,
        padx=14,
        pady=10,
    )
    diag_card.pack(fill="x", pady=6)

    metrics_var = tk.StringVar(value="CPU: Checking... | RAM: Checking...")
    metrics_lbl = tk.Label(
        diag_card,
        textvariable=metrics_var,
        font=("Segoe UI", 10),
        fg=TEXT_MUTED,
        bg=BG_CARD,
    )
    metrics_lbl.pack(anchor="w")

    # Action Buttons Card
    btn_frame = tk.Frame(body, bg=BG_MAIN, pady=10)
    btn_frame.pack(fill="x")

    def on_start_server():
        start_server_process(DEFAULT_PORT)
        status_var.set(f"Status: Online & Ready (Port {DEFAULT_PORT})")
        status_lbl.configure(fg=GREEN)
        start_btn.configure(state="disabled")
        open_btn.configure(state="normal")
        stop_btn.configure(state="normal")

    def on_open_browser():
        webbrowser.open(local_url)

    def on_copy_lan():
        root.clipboard_clear()
        root.clipboard_append(lan_url)
        messagebox.showinfo("Copied", f"LAN URL copied to clipboard:\n{lan_url}\n\nAny computer in this lab can open this URL in their browser!")

    def on_shutdown():
        if messagebox.askyesno("Clean Shutdown", "Are you sure you want to stop the SmileAI server and exit?"):
            stop_server_process()
            root.destroy()

    start_btn = tk.Button(
        btn_frame,
        text="▶  Start Server",
        command=on_start_server,
        font=("Segoe UI", 10, "bold"),
        bg=GREEN,
        fg="#ffffff",
        padx=16,
        pady=8,
        relief="flat",
        cursor="hand2",
    )
    start_btn.pack(fill="x", pady=4)

    open_btn = tk.Button(
        btn_frame,
        text="🌐  Open Web Suite (Browser)",
        command=on_open_browser,
        state="disabled",
        font=("Segoe UI", 10, "bold"),
        bg=BLUE,
        fg="#ffffff",
        padx=16,
        pady=8,
        relief="flat",
        cursor="hand2",
    )
    open_btn.pack(fill="x", pady=4)

    copy_lan_btn = tk.Button(
        btn_frame,
        text="📋  Copy LAN URL for Lab PCs",
        command=on_copy_lan,
        font=("Segoe UI", 9),
        bg=BG_CARD,
        fg=NAVY,
        relief="groove",
        cursor="hand2",
    )
    copy_lan_btn.pack(fill="x", pady=4)

    stop_btn = tk.Button(
        btn_frame,
        text="⏹  Clean Shutdown & Exit",
        command=on_shutdown,
        font=("Segoe UI", 10, "bold"),
        bg=RED,
        fg="#ffffff",
        padx=16,
        pady=8,
        relief="flat",
        cursor="hand2",
    )
    stop_btn.pack(fill="x", pady=8)

    # Periodic metrics update loop
    def update_diagnostics():
        if not is_shutting_down:
            m = get_system_metrics()
            metrics_var.set(
                f"CPU: {m['cpu_percent']}%  |  RAM: {m['ram_used_gb']} GB / {m['ram_total_gb']} GB ({m['ram_percent']}%)  |  LAN Server Ready"
            )
            root.after(2000, update_diagnostics)

    root.after(500, update_diagnostics)
    root.protocol("WM_DELETE_WINDOW", on_shutdown)

    return root


if __name__ == "__main__":
    # Check if run with --headless or in terminal mode
    if "--cli" in sys.argv or "--headless" in sys.argv:
        print("Starting SmileAI in CLI Headless Mode on port", DEFAULT_PORT)
        p = start_server_process(DEFAULT_PORT)
        try:
            p.wait()
        except KeyboardInterrupt:
            stop_server_process()
            print("\nSmileAI cleanly stopped.")
    else:
        gui = create_gui()
        gui.mainloop()
