"""Refresh prod-deliverables/ — the folder you hand a client."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from app.config_load import ROOT
from app.package_check import format_report, run_package_check
from app.server import local_ip

OUT = ROOT / "prod-deliverables"

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "data",
    "uploads",
    "prod-deliverables",
    "agent-transcripts",
    "node_modules",
}

SKIP_SUFFIXES = {".pyc", ".pyo", ".zip", ".sqlite3", ".db"}


def write_deliverables(*, make_zip: bool = False) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "README.md": _readme(),
        "PACKING-LIST.md": _packing_list(),
        "TEST-PLAN.md": _test_plan(),
        "FIREWALL-AND-SHUTDOWN.md": _firewall(),
        "config.example.yaml": _example_config(),
    }
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8")

    check = run_package_check()
    (OUT / "package-check.txt").write_text(format_report(check), encoding="utf-8")

    zip_path = None
    if make_zip:
        zip_path = OUT / "EduRAG-client.zip"
        _write_zip(zip_path)

    report_lines = [
        f"Wrote {OUT}",
        f"LAN hint: http://{local_ip()}:4747",
        "OK" if check.get("ok") else "package-check has FAIL items — see package-check.txt",
    ]
    if zip_path:
        report_lines.append(f"Zip: {zip_path}")
    return {
        "ok": bool(check.get("ok")),
        "dir": str(OUT),
        "zip": str(zip_path) if zip_path else None,
        "report": "\n".join(report_lines),
        "check": check,
    }


def _readme() -> str:
    return """# EduRAG — client test pack

Local LAN learning assistant. Nothing is sent to the cloud. Port **4747** only.

## On the test PC

1. Unzip / copy the appliance folder (see PACKING-LIST.md).
2. Right-click **Setup-EduRAG.bat** → Run as administrator (first time).
3. Later days: double-click **Start-EduRAG.bat**. Leave that window open.
4. This PC: http://127.0.0.1:4747  
   Other devices on the same Wi-Fi: the LAN URL printed in the Start window.

## Demo seats

| Seat    | Email                  | Password    |
|---------|------------------------|-------------|
| Admin   | admin@edurag.local     | admin123    |
| Teacher | teacher@edurag.local   | teacher123  |
| Student | student@edurag.local   | student123  |

Click a seat on the sign-in screen. Change these passwords before a real class.

## Stop (required)

Double-click **Stop-EduRAG.bat**. That unloads the chat model from VRAM and frees port 4747. Do not only kill the window if you can help it.

## Do not

- Bind 8080 or 3636
- Point config at a cloud API
- Open 4747 on the Public firewall profile
- Copy `data/` or `config.yaml` JWT secrets between sites

Read TEST-PLAN.md before you sign off.
"""


def _packing_list() -> str:
    return """# What to copy for a client

From the build PC, copy this tree (or run `python -m app pack-client --zip`):

```
EduRAG/
  app/
  web/
  models/          (embedding + OCR weights)
  scripts/
  tests/           (optional)
  Setup-EduRAG.bat
  Start-EduRAG.bat
  Stop-EduRAG.bat
  requirements.txt
  README.md
  docs/            (architecture + CLI; skip private-room.md for school clients)
  prod-deliverables/   (this folder)
```

## Leave out

- `.venv/` / `runtime/` — Setup creates these on the client PC
- `data/` — local chats, uploads, companion key
- `config.yaml` — contains a machine JWT secret; client runs `python -m app model-discovery` or Setup
- `.git/`
- `prod-deliverables/*.zip` (do not nest zips)

## After copy

On the client PC: Setup-EduRAG.bat once, then Start-EduRAG.bat.  
Confirm `python -m app package-check` is all OK.
"""


def _test_plan() -> str:
    return """# Client test plan

Do these on the server PC and one phone/laptop on the same Wi-Fi.

1. Start-EduRAG.bat opens http://127.0.0.1:4747. Sign in as Teacher.
2. New library → upload a small PDF or index a folder. Wait until the job finishes.
3. Ask Tutor a question that is in the file. You should see a cited answer, not an invention.
4. Sign out. Sign in as Student. Same library is visible. Chat works.
5. From another device, open `http://<server-lan-ip>:4747` (printed in the Start window). Sign in. Chat works.
6. Mark the library K-12. Ask something off-tone; it should stay school-conservative.
7. Stop-EduRAG.bat. Port 4747 should be free. GPU memory for the chat model should drop (Task Manager → GPU).
8. Start again. Demo logins still work.

## Fail if

- The UI is reachable on the internet (it must be LAN/Private only)
- Answers cite files that were never ingested
- Start uses port 8080 or 3636
- Closing the window leaves the 7B model loaded in VRAM for hours (Stop.bat should unload it)
"""


def _firewall() -> str:
    return """# Firewall and shutdown

## Inbound LAN (port 4747)

Setup-EduRAG.bat (as Administrator) adds:

```
netsh advfirewall firewall add rule name="EduRAG" dir=in action=allow protocol=TCP localport=4747 profile=private
```

- Profile **Private** only — not Public, not Domain unless you intend that.
- Do not open 11434 (Ollama) to the LAN. Only the EduRAG PC talks to Ollama on localhost.
- Phones must be on the same Wi-Fi as the server PC.

To re-apply without full Setup, run `scripts\\firewall-edurag.ps1` elevated.

## Safe close

1. Stop-EduRAG.bat  
   Unloads `qwen2.5:7b-instruct` from VRAM (`keep_alive=0`) and stops the process listening on 4747.
2. Ctrl+C in the Start window also unloads the model (FastAPI shutdown hook).
3. Closing the window with X may skip unload — run Stop-EduRAG.bat after.

Ollama itself can stay installed. We do not leave the 7B weights sitting in 12 GB VRAM.

## Memory budget (RTX 3060 12 GB / 32 GB RAM)

- LLM: Ollama, context 4096, keep_alive **5m**, one model, one parallel slot
- Embeddings: MiniLM ONNX on **CPU**, 2 threads
- OCR: EasyOCR **CPU**, only when a scan has no text
- Do not set `num_gpu: 99` (that tries to pin every layer and can starve the desktop)
"""


def _example_config() -> str:
    return """server:
  host: 0.0.0.0
  port: 4747
llm:
  provider: ollama
  model: qwen2.5:7b-instruct
  path: ollama://qwen2.5:7b-instruct
  base_url: http://localhost:11434
  num_ctx: 4096
  num_predict: 2048
  temperature: 0.3
  keep_alive: 5m
resources:
  ollama_keep_alive: 5m
  ollama_max_loaded_models: 1
  ollama_num_parallel: 1
  onnx_threads: 2
  llm_threads: 4
  llm_batch: 256
  unload_llm_on_stop: true
embedding:
  model: all-MiniLM-L6-v2
  path: models/embedding/all-MiniLM-L6-v2
  device: cpu
reranker:
  enabled: false
  device: cpu
ocr:
  engine: easyocr
  path: models/ocr
  enabled: true
tts:
  enabled: false
"""


def _write_zip(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if path.name == "config.yaml":
                continue
            if path.name in {"companion.json", "companion.key"}:
                continue
            rel = path.relative_to(ROOT)
            zf.write(path, arcname=str(rel))
        example = OUT / "config.example.yaml"
        if example.is_file():
            zf.write(example, arcname="config.example.yaml")
        for extra in OUT.iterdir():
            if extra.is_file() and extra.suffix.lower() in {".md", ".yaml", ".txt"}:
                zf.write(extra, arcname="prod-deliverables/" + extra.name)
