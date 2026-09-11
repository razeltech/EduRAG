"""Automated Build & Packaging Pipeline for EduRAG Standalone Release.
Compiles app/launcher.py with PyInstaller into EduRAG-Server.exe.
Excludes all companion code, strips all .bat files, and bundles web assets,
offline models, and documentation into a standalone deliverable folder.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT = ROOT / "EduRAG-Release"
BUILD_DIR = ROOT / "build_cache"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or ROOT, check=False)
    if result.returncode != 0:
        print(f"Error: Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def clean_previous_builds() -> None:
    print("\n[1/6] Cleaning previous build artifacts...")
    for folder in (DIST_ROOT, BUILD_DIR, ROOT / "dist"):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    print("[OK] Cleaned build directories.")


def compile_executable() -> None:
    print("\n[2/6] Compiling EduRAG-Server.exe with PyInstaller...")

    hidden_imports = [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "pydantic",
        "pydantic_core",
        "onnxruntime",
        "tokenizers",
        "yaml",
        "httpx",
        "rich",
        "psutil",
        "fitz",
        "docx",
        "pptx",
        "bs4",
        "sqlite3",
        "app.server",
        "app.db",
        "app.db.store",
        "app.pipeline",
        "app.rag",
        "app.chunker",
        "app.embed",
        "app.llm",
        "app.system_info",
        "app.shutdown",
        "app.model_downloader",
        "app.auth",
        "app.bootstrap",
        "app.fsbrowse",
        "app.jobs",
        "app.personas",
        "app.rerank",
        "app.retrieve",
        "app.safety",
        "app.ingest.pdf",
        "app.ingest.docx_ingest",
        "app.ingest.pptx_ingest",
        "app.ingest.html_ingest",
        "app.ingest.ocr",
        "app.ingest.scanner",
        "app.ingest.service",
    ]

    excludes = [
        "onnx",
        "tensorflow",
        "keras",
        "jax",
        "jaxlib",
        "kubernetes",
        "torchvision",
        "torchaudio",
        "nltk",
        "pandas",
        "scipy",
        "matplotlib",
        "tkinter",
        "pytest",
        "tests",
        "llvmlite",
        "numba",
        "av",
        "sklearn",
        "hf_xet",
        "Pythonwin",
        "app.companion",
        "app.companion_engine",
        "app.companion_image",
        "app.companion_jobs",
        "app.companion_sdxl",
    ]

    data_items = [
        f"{ROOT / 'app' / 'db' / 'schema.sql'};app/db",
    ]

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name",
        "EduRAG-Server",
        "--workpath",
        str(BUILD_DIR / "work"),
        "--distpath",
        str(BUILD_DIR / "dist"),
        "--specpath",
        str(BUILD_DIR),
        str(ROOT / "app" / "launcher.py"),
    ]

    for hi in hidden_imports:
        pyinstaller_cmd.extend(["--hidden-import", hi])
    for ex in excludes:
        pyinstaller_cmd.extend(["--exclude-module", ex])
    for d in data_items:
        pyinstaller_cmd.extend(["--add-data", d])

    run_cmd(pyinstaller_cmd)
    print("[OK] Compilation completed successfully.")


def assemble_deliverables() -> None:
    print("\n[3/6] Assembling release folder structure...")
    compiled_dist = BUILD_DIR / "dist" / "EduRAG-Server"
    if not compiled_dist.is_dir():
        print(f"Error: Compiled directory not found at {compiled_dist}", file=sys.stderr)
        sys.exit(1)

    # 1. Copy compiled binary & _internal folder
    for item in compiled_dist.iterdir():
        dest = DIST_ROOT / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 2. Copy Web assets (strictly excluding companion files)
    print("\n[4/6] Copying pure educational web assets (excluding companion)...")
    web_dest = DIST_ROOT / "web"
    web_dest.mkdir(parents=True, exist_ok=True)
    allowed_web = {"index.html", "app.js", "styles.css"}
    for f in (ROOT / "web").iterdir():
        if f.is_file() and f.name in allowed_web:
            shutil.copy2(f, web_dest / f.name)
            print(f"  + web/{f.name}")

    # 3. Copy Offline Models (Embedding + OCR)
    print("\n[5/6] Copying offline embedding & OCR models...")
    models_dest = DIST_ROOT / "models"
    models_dest.mkdir(parents=True, exist_ok=True)

    # MiniLM ONNX Embedding
    emb_src = ROOT / "models" / "embedding" / "all-MiniLM-L6-v2"
    if emb_src.is_dir():
        shutil.copytree(emb_src, models_dest / "embedding" / "all-MiniLM-L6-v2", dirs_exist_ok=True)
        print("  + models/embedding/all-MiniLM-L6-v2")

    # OCR Models (English detector + weights)
    ocr_src = ROOT / "models" / "ocr"
    if ocr_src.is_dir():
        ocr_dest = models_dest / "ocr"
        ocr_dest.mkdir(parents=True, exist_ok=True)
        for ocr_file in ("craft_mlt_25k.pth", "english_g2.pth"):
            src_file = ocr_src / ocr_file
            if src_file.is_file():
                shutil.copy2(src_file, ocr_dest / ocr_file)
                print(f"  + models/ocr/{ocr_file}")

    # 4. Generate clean config.yaml
    clean_config = (
        "server:\n"
        "  host: 0.0.0.0\n"
        "  port: 4747\n"
        "llm:\n"
        "  provider: ollama\n"
        "  model: qwen2.5:7b-instruct\n"
        "  base_url: http://localhost:11434\n"
        "  num_ctx: 4096\n"
        "  num_predict: 2048\n"
        "  temperature: 0.3\n"
        "  keep_alive: 5m\n"
        "embedding:\n"
        "  model: all-MiniLM-L6-v2\n"
        "  path: models/embedding/all-MiniLM-L6-v2\n"
        "  device: cpu\n"
        "ocr:\n"
        "  engine: easyocr\n"
        "  path: models/ocr\n"
        "  enabled: true\n"
    )
    (DIST_ROOT / "config.yaml").write_text(clean_config, encoding="utf-8")
    print("  + config.yaml (clean default)")

    # 5. Create testing documentation (README-TESTING.md)
    readme_text = (
        "# EduRAG — Standalone Appliance Guide\n\n"
        "## Setup for 1 Server PC + 5 Connected Client PCs\n\n"
        "### Step 1: On the Server PC\n"
        "1. Double-click `EduRAG-Server.exe`.\n"
        "2. The launcher will assess your hardware (RAM, GPU/VRAM) and recommend the best model.\n"
        "3. If Ollama is not installed, it will offer to automatically download and run the installer.\n"
        "4. Choose or accept your model storage path (e.g. `D:\\OllamaModels` if C: drive is low on space).\n"
        "5. The server will download the model with a live progress bar and launch on port `4747`.\n\n"
        "### Step 2: On the 5 Client PCs (LAN / Wi-Fi)\n"
        "**Zero installation or Python needed on the client PCs!**\n"
        "1. Ensure the 5 PCs are connected to the same Wi-Fi or Ethernet switch as the Server PC.\n"
        "2. Open any web browser (Google Chrome, Microsoft Edge, Mozilla Firefox).\n"
        "3. In the address bar, type the Server LAN URL displayed in the launcher window (e.g. `http://192.168.1.15:4747`).\n"
        "4. Sign in using any of the demo accounts:\n"
        "   - **Teacher:** `teacher@edurag.local` / `teacher123`\n"
        "   - **Student:** `student@edurag.local` / `student123`\n"
        "   - **Admin:** `admin@edurag.local` / `admin123`\n\n"
        "### Firewall Note\n"
        "If client PCs cannot reach the server, allow port 4747 in Windows Defender Firewall:\n"
        "Run PowerShell as Administrator on the Server PC:\n"
        "```powershell\n"
        'New-NetFirewallRule -DisplayName "EduRAG Server" -Direction Inbound -LocalPort 4747 -Protocol TCP -Action Allow -Profile Private\n'
        "```\n\n"
        "### Stopping the Server\n"
        "Press `Ctrl+C` in the `EduRAG-Server.exe` window to safely stop the server and release GPU memory.\n"
    )
    (DIST_ROOT / "README-TESTING.md").write_text(readme_text, encoding="utf-8")
    print("  + README-TESTING.md")


def verify_deliverable_integrity() -> None:
    print("\n[6/6] Verifying deliverable integrity & security constraints...")

    # Check 1: EduRAG-Server.exe exists
    exe_path = DIST_ROOT / "EduRAG-Server.exe"
    if not exe_path.is_file():
        raise RuntimeError("FATAL: EduRAG-Server.exe was not created!")
    print(f"[OK] Verified executable: {exe_path.name} ({round(exe_path.stat().st_size / 1024, 1)} KB)")

    # Check 2: No raw .py files in user-accessible folders
    for item in DIST_ROOT.iterdir():
        if item.is_file() and item.suffix.lower() == ".py":
            raise RuntimeError(f"FATAL: Raw python file found in release root: {item.name}")
    for item in (DIST_ROOT / "web").iterdir():
        if item.is_file() and item.suffix.lower() == ".py":
            raise RuntimeError(f"FATAL: Python file found in web directory: {item.name}")
    print("[OK] Verified IP Protection: Zero .py files in release root and web folder.")

    # Check 3: Zero .bat files in release
    for item in DIST_ROOT.rglob("*.bat"):
        raise RuntimeError(f"FATAL: Prohibited .bat file found in release: {item.relative_to(DIST_ROOT)}")
    print("[OK] Verified Zero .bat files: No batch scripts present in release.")

    # Check 4: Zero companion files in web and root
    for item in DIST_ROOT.rglob("*companion*"):
        raise RuntimeError(f"FATAL: Companion file leaked into release: {item.relative_to(DIST_ROOT)}")
    print("[OK] Verified Companion Exclusion: Zero companion assets or code in release.")

    print("\n" + "=" * 60)
    print(" RELEASE BUILD COMPLETED SUCCESSFULLY!")
    print(f" Output Location: {DIST_ROOT}")
    print("=" * 60)


def main():
    clean_previous_builds()
    compile_executable()
    assemble_deliverables()
    verify_deliverable_integrity()


if __name__ == "__main__":
    main()
