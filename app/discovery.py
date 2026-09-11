"""Scan local model files and known caches. Writes config.yaml. No downloads."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
CONFIG_PATH = ROOT / "config.yaml"

IMAGE_GGUF_HINTS = ("flux", "sdxl", "sd3", "unet", "diffusion", "shuttle")
LLM_NAME_HINTS = (
    "qwen",
    "gpt-oss",
    "llama",
    "mistral",
    "phi",
    "gemma",
    "yi",
    "deepseek",
    "instruct",
)
EMBED_HINTS = ("bge", "e5", "gte", "minilm", "nomic", "embedding", "embed")
RERANK_HINTS = ("rerank", "ms-marco", "cross-encoder", "bge-reranker")
OCR_HINTS = ("easyocr", "craft", "paddleocr", "tesseract", "devanagari")
TTS_HINTS = ("piper", "parler", "kokoro")


@dataclass
class FoundModel:
    role: str
    status: str  # FOUND | MISSING | SKIPPED
    name: str
    path: str | None = None
    source: str | None = None
    format: str | None = None
    size_mb: float | None = None
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _size_mb(path: Path) -> float | None:
    try:
        if path.is_file():
            return round(path.stat().st_size / (1024 * 1024), 1)
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return round(total / (1024 * 1024), 1)
    except OSError:
        return None


def _is_image_model(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in IMAGE_GGUF_HINTS)


def _classify_folder_or_file(name: str) -> str | None:
    n = name.lower()
    if any(h in n for h in RERANK_HINTS):
        return "reranker"
    if any(h in n for h in EMBED_HINTS):
        return "embedding"
    if any(h in n for h in OCR_HINTS):
        return "ocr"
    if any(h in n for h in TTS_HINTS):
        return "tts"
    if n.endswith(".gguf") or any(h in n for h in LLM_NAME_HINTS):
        return "llm"
    return None


def _scan_project_models() -> list[FoundModel]:
    found: list[FoundModel] = []
    role_dirs = {
        "llm": MODELS_DIR / "llm",
        "embedding": MODELS_DIR / "embedding",
        "reranker": MODELS_DIR / "reranker",
        "ocr": MODELS_DIR / "ocr",
        "tts": MODELS_DIR / "tts",
    }
    for role, folder in role_dirs.items():
        folder.mkdir(parents=True, exist_ok=True)
        entries = [
            p
            for p in folder.iterdir()
            if p.name not in {".gitkeep", ".gitignore"} and not p.name.startswith(".")
        ]
        if not entries:
            continue
        for p in entries:
            if _is_image_model(p.name):
                found.append(
                    FoundModel(
                        role=role,
                        status="SKIPPED",
                        name=p.name,
                        path=str(p),
                        source="models/",
                        format=p.suffix.lstrip(".") or "dir",
                        size_mb=_size_mb(p),
                        notes="Looks like an image/diffusion model, not used for RAG.",
                    )
                )
                continue
            fmt = "dir"
            if p.is_file():
                fmt = p.suffix.lstrip(".").lower() or "file"
            elif (p / "config.json").exists() and (p / "onnx").exists():
                fmt = "onnx-st"
            elif (p / "modules.json").exists() or (p / "config.json").exists():
                fmt = "sentence-transformers"
            found.append(
                FoundModel(
                    role=role,
                    status="FOUND",
                    name=p.name,
                    path=str(p),
                    source="models/",
                    format=fmt,
                    size_mb=_size_mb(p),
                )
            )
    return found


def _ollama_models() -> list[FoundModel]:
    found: list[FoundModel] = []
    if not shutil.which("ollama"):
        return found
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return found
    if result.returncode != 0:
        return found
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        # ollama list: NAME ID SIZE UNIT MODIFIED...
        if len(parts) >= 4 and parts[3] in {"B", "KB", "MB", "GB", "TB"}:
            size = f"{parts[2]} {parts[3]}"
        else:
            size = parts[2]
        role = "llm"
        notes = None
        if "coder" in name.lower() and "instruct" not in name.lower():
            notes = "Coder variant — usable as a fallback LLM, not the first choice for tutoring."
        if _is_image_model(name):
            continue
        found.append(
            FoundModel(
                role=role,
                status="FOUND",
                name=name,
                path=f"ollama://{name}",
                source="ollama",
                format="ollama",
                notes=notes,
                extra={"size": size, "id": parts[1] if len(parts) > 1 else None},
            )
        )
    return found


def _scan_hf_hub(hub: Path) -> list[FoundModel]:
    found: list[FoundModel] = []
    if not hub.is_dir():
        return found
    for child in hub.iterdir():
        if not child.is_dir() or not child.name.startswith("models--"):
            continue
        pretty = child.name.replace("models--", "").replace("--", "/")
        if _is_image_model(pretty):
            found.append(
                FoundModel(
                    role="other",
                    status="SKIPPED",
                    name=pretty,
                    path=str(child),
                    source="huggingface",
                    format="hf-hub",
                    notes="Image/diffusion checkpoint — ignored for RAG.",
                )
            )
            continue
        role = _classify_folder_or_file(pretty) or "other"
        found.append(
            FoundModel(
                role=role,
                status="FOUND",
                name=pretty,
                path=str(child),
                source="huggingface",
                format="hf-hub",
                size_mb=_size_mb(child),
            )
        )
    return found


def _scan_known_paths() -> list[FoundModel]:
    found: list[FoundModel] = []
    home = Path.home()
    candidates: list[tuple[str, Path, str]] = [
        (
            "embedding",
            home
            / ".vscode"
            / "extensions"
            / "continue.continue-2.0.0-win32-x64"
            / "models"
            / "all-MiniLM-L6-v2",
            "continue-extension",
        ),
        ("ocr", home / ".EasyOCR" / "model", "easyocr"),
        (
            "tts",
            Path(r"D:\ReactApps2Git\smilai\backend\models\hf_cache\piper"),
            "smilai",
        ),
        (
            "tts",
            Path(r"D:\ReactApps2Git\athena-starter\athena\data\models\piper"),
            "athena",
        ),
    ]

    # Continue may be installed under a different version folder.
    vscode_ext = home / ".vscode" / "extensions"
    if vscode_ext.is_dir():
        for ext in vscode_ext.glob("continue.continue-*/models/all-MiniLM-L6-v2"):
            candidates.append(("embedding", ext, "continue-extension"))

    cursor_ext = home / ".cursor" / "extensions"
    if cursor_ext.is_dir():
        for ext in cursor_ext.glob("continue.continue-*/models/all-MiniLM-L6-v2"):
            candidates.append(("embedding", ext, "continue-extension"))

    seen: set[str] = set()
    for role, path, source in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if not path.exists():
            continue
        files = []
        if path.is_dir():
            files = [p.name for p in path.iterdir() if p.is_file() or p.is_dir()]
        found.append(
            FoundModel(
                role=role,
                status="FOUND",
                name=path.name,
                path=str(path),
                source=source,
                format="dir",
                size_mb=_size_mb(path),
                extra={"contents": files[:12]},
            )
        )
    return found


def _pick_primary(found: list[FoundModel], role: str) -> FoundModel | None:
    hits = [m for m in found if m.role == role and m.status == "FOUND"]
    if not hits:
        return None
    if role == "llm":
        preferred = [
            "qwen2.5:7b-instruct",
            "qwen2.5:7b",
            "gpt-oss:20b",
            "qwen2.5:14b",
        ]
        for name in preferred:
            for m in hits:
                if m.name == name or m.name.startswith(name):
                    return m
        instruct = [m for m in hits if "instruct" in m.name.lower()]
        if instruct:
            return instruct[0]
        non_coder = [m for m in hits if "coder" not in m.name.lower()]
        if non_coder:
            return non_coder[0]
    if role == "embedding":
        for m in hits:
            if "bge-small" in m.name.lower():
                return m
        for m in hits:
            if "minilm" in m.name.lower():
                return m
    return hits[0]


def discover() -> dict[str, Any]:
    found: list[FoundModel] = []
    found.extend(_scan_project_models())
    found.extend(_ollama_models())
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    found.extend(_scan_hf_hub(hf_home / "hub"))
    found.extend(_scan_hf_hub(Path.home() / ".cache" / "huggingface" / "hub"))
    found.extend(_scan_known_paths())

    roles = ["llm", "embedding", "reranker", "ocr"]
    primaries: dict[str, FoundModel | None] = {r: _pick_primary(found, r) for r in roles}
    tts = _pick_primary(found, "tts")

    recommendations: list[str] = []
    if primaries["llm"] is None:
        recommendations.append(
            "No chat LLM found. Pull one with: ollama pull qwen2.5:7b-instruct"
        )
    elif "coder" in (primaries["llm"].name or "").lower() and "instruct" not in (
        primaries["llm"].name or ""
    ).lower():
        recommendations.append(
            f"Primary LLM is a coder model ({primaries['llm'].name}). "
            "Prefer qwen2.5:7b-instruct for tutoring."
        )

    if primaries["embedding"] is None:
        recommendations.append(
            "Embedding model missing — retrieval cannot run until one is added. "
            "Smallest good option: BAAI/bge-small-en-v1.5 (~130 MB) or all-MiniLM-L6-v2."
        )
    elif "minilm" in (primaries["embedding"].name or "").lower():
        recommendations.append(
            "Using all-MiniLM-L6-v2 for embeddings. Fine to start; "
            "BAAI/bge-small-en-v1.5 is a quality upgrade (~130 MB) if you add it later."
        )

    if primaries["reranker"] is None:
        recommendations.append(
            "Reranker missing — retrieval will run without reranking until one is added. "
            "System is still usable in degraded mode. "
            "Suggested: cross-encoder/ms-marco-MiniLM-L-6-v2 (~80 MB)."
        )

    if primaries["ocr"] is None:
        recommendations.append(
            "OCR missing — scanned textbook pages will be skipped until an OCR model is added."
        )
    else:
        recommendations.append(
            "EasyOCR weights found (English detector + Devanagari). "
            "Native-text PDF extraction still runs first; OCR is fallback only."
        )

    if tts:
        recommendations.append(
            f"Piper TTS voice found at {tts.path}. Not required for Phase 0–8; kept for later voice."
        )

    report = {
        "primaries": {k: (asdict(v) if v else None) for k, v in primaries.items()},
        "tts": asdict(tts) if tts else None,
        "all": [asdict(m) for m in found],
        "recommendations": recommendations,
    }
    return report


def format_report(report: dict[str, Any]) -> str:
    lines = ["MODEL DISCOVERY", "================"]

    def line_for(role: str, label: str | None = None) -> str:
        key = label or role
        item = report["primaries"].get(role) if role != "tts" else report.get("tts")
        tag = key.upper() + ":"
        tag = f"{tag:<12}"
        if not item:
            return f"{tag}[MISSING]"
        loc = item.get("path") or item.get("name")
        extra = ""
        if item.get("format"):
            extra += f"  ({item['format']}"
            if item.get("extra", {}).get("size"):
                extra += f", size: {item['extra']['size']}"
            elif item.get("size_mb") is not None:
                extra += f", {item['size_mb']} MB"
            extra += ")"
        src = f"  [{item.get('source')}]" if item.get("source") else ""
        return f"{tag}[FOUND] {loc}{extra}{src}"

    lines.append(line_for("llm"))
    lines.append(line_for("embedding"))
    lines.append(line_for("reranker"))
    lines.append(line_for("ocr"))
    if report.get("tts"):
        lines.append(line_for("tts", "tts"))
    lines.append("")
    lines.append("Recommendation:")
    for rec in report["recommendations"]:
        lines.append(f"  - {rec}")

    extras = [
        m
        for m in report["all"]
        if m["status"] == "FOUND"
        and m["path"]
        not in {
            (report["primaries"].get(r) or {}).get("path")
            for r in ("llm", "embedding", "reranker", "ocr")
        }
        and m["path"] != (report.get("tts") or {}).get("path")
    ]
    if extras:
        lines.append("")
        lines.append("Also found:")
        for m in extras:
            lines.append(f"  - [{m['role']}] {m['name']}  ({m.get('source')})")
    return "\n".join(lines)


def write_config(report: dict[str, Any], system: dict[str, Any] | None = None) -> Path:
    from app.config_load import load_config
    from app.llm import DEFAULT_MODELS

    primaries = report["primaries"]
    llm = primaries.get("llm") or {}
    embed = primaries.get("embedding") or {}
    rerank = primaries.get("reranker") or {}
    ocr = primaries.get("ocr") or {}
    tts = report.get("tts") or {}
    prev_llm = (load_config().get("llm") or {})
    models_catalog = prev_llm.get("models") or DEFAULT_MODELS

    config = {
        "server": {
            "host": "0.0.0.0",
            "port": 4747,
        },
        "hardware": {
            "gpu": (system or {}).get("gpu", {}).get("name"),
            "vram_gb": (system or {}).get("vram_gb"),
            "ram_gb": (system or {}).get("ram_gb"),
        },
        "llm": {
            "provider": "ollama" if (llm.get("source") == "ollama") else "gguf",
            "model": llm.get("name") or prev_llm.get("model") or "qwen2.5:7b-instruct",
            "path": llm.get("path") or prev_llm.get("path") or "ollama://qwen2.5:7b-instruct",
            "base_url": prev_llm.get("base_url") or "http://localhost:11434",
            "num_ctx": prev_llm.get("num_ctx") or 4096,
            "num_predict": prev_llm.get("num_predict") or 2048,
            "temperature": prev_llm.get("temperature") or 0.3,
            "keep_alive": prev_llm.get("keep_alive") or "5m",
            "models": models_catalog,
        },
        "embedding": {
            "model": embed.get("name"),
            "path": embed.get("path"),
            "device": "cpu",
        },
        "reranker": {
            "model": rerank.get("name"),
            "path": rerank.get("path"),
            "device": "cpu",
            "enabled": bool(rerank),
        },
        "ocr": {
            "engine": "easyocr" if ocr else None,
            "path": ocr.get("path"),
            "enabled": bool(ocr),
        },
        "tts": {
            "engine": "piper" if tts else None,
            "path": tts.get("path"),
            "enabled": False,
        },
        "degraded_modes": {
            "reranker": not bool(rerank),
            "ocr": not bool(ocr),
            "embedding": not bool(embed),
        },
        "discovery": {
            "recommendations": report["recommendations"],
        },
    }
    CONFIG_PATH.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return CONFIG_PATH
