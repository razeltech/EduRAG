"""EduRAG Server Launcher.
Cross-platform pure Python runner with zero batch file dependency.
"""
from __future__ import annotations

import os
import sys
import webbrowser
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def main():
    os.environ.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")
    os.environ.setdefault("OLLAMA_NUM_PARALLEL", "1")
    os.environ.setdefault("OLLAMA_KEEP_ALIVE", "5m")
    os.environ.setdefault("OLLAMA_FLASH_ATTENTION", "1")

    # If launcher is available, run it
    try:
        from app.launcher import main as launcher_main
        launcher_main()
    except Exception as exc:
        print(f"Starting standard server: {exc}")
        def open_browser():
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:4747")
        threading.Thread(target=open_browser, daemon=True).start()

        import uvicorn
        uvicorn.run("app.server:app", host="0.0.0.0", port=4747, log_level="info")

if __name__ == "__main__":
    main()
