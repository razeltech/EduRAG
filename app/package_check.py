"""Checklist for copying this appliance to a second institution PC."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config_load import ROOT, load_config

FORBIDDEN_PORTS = {8080, 3636}


def run_package_check() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def ok(name: str, detail: str = "") -> None:
        checks.append({"name": name, "ok": True, "detail": detail})

    def fail(name: str, detail: str) -> None:
        checks.append({"name": name, "ok": False, "detail": detail})

    required = [
        ROOT / "app" / "server.py",
        ROOT / "app" / "db" / "schema.sql",
        ROOT / "web" / "index.html",
        ROOT / "web" / "app.js",
        ROOT / "web" / "styles.css",
        ROOT / "Start-EduRAG.bat",
        ROOT / "Stop-EduRAG.bat",
        ROOT / "Setup-EduRAG.bat",
        ROOT / "README.md",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    if missing:
        fail("core files", "Missing: " + ", ".join(missing))
    else:
        ok("core files", f"{len(required)} present")

    cfg = load_config()
    if not cfg:
        fail("config.yaml", "Missing or empty. Run python -m app model-discovery.")
    else:
        ok("config.yaml", str(ROOT / "config.yaml"))

    port = int((cfg.get("server") or {}).get("port") or 4747)
    if port in FORBIDDEN_PORTS:
        fail("port", f"Port {port} is reserved. Use 4747.")
    else:
        ok("port", str(port))

    embed = (cfg.get("embedding") or {}).get("path")
    embed_path = Path(embed) if embed else ROOT / "models" / "embedding"
    if embed_path.exists():
        ok("embedding", str(embed_path))
    else:
        fail("embedding", f"Not found: {embed_path}")

    rerank_path = (cfg.get("reranker") or {}).get("path")
    rerank_dir = Path(rerank_path) if rerank_path else ROOT / "models" / "reranker"
    rerank_files = [
        p
        for p in rerank_dir.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    ] if rerank_dir.exists() else []
    if rerank_files:
        ok("reranker", str(rerank_dir))
    else:
        warnings.append(
            "No cross-encoder in models/reranker/. Lexical rerank is on; add "
            "ms-marco-MiniLM-L-6-v2 later for better ranking."
        )
        ok("reranker", "lexical fallback (no cross-encoder on disk)")

    ocr_path = (cfg.get("ocr") or {}).get("path")
    ocr_dir = Path(ocr_path) if ocr_path else ROOT / "models" / "ocr"
    if ocr_dir.exists():
        ok("ocr", str(ocr_dir))
    else:
        warnings.append(f"OCR path missing: {ocr_dir}. Scanned PDFs will skip OCR.")
        ok("ocr", "missing (degraded)")

    llm = (cfg.get("llm") or {}).get("model") or ""
    if llm:
        ok("llm", llm)
    else:
        fail("llm", "No model in config. Run setup / Ollama pull.")

    try:
        from app.db import init_db
        from app.personas import DEFAULT_PERSONA_ID, REGISTRY

        conn = init_db()
        n_tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        conn.close()
        ok("database", f"{n_tables} tables")
        if DEFAULT_PERSONA_ID not in REGISTRY:
            fail("personas", f"Default {DEFAULT_PERSONA_ID} missing")
        else:
            ok("personas", f"{len(REGISTRY)} loaded, default={DEFAULT_PERSONA_ID}")
    except Exception as exc:
        fail("database", str(exc))

    fatal = [c for c in checks if not c["ok"]]
    return {
        "ok": not fatal,
        "ready_for_second_institution": not fatal,
        "checks": checks,
        "warnings": warnings,
        "copy": [
            "Copy the whole EduRAG folder (app, web, models, Start/Stop/Setup bats).",
            "Or run python -m app pack-client --zip and send prod-deliverables/EduRAG-client.zip.",
            "On the new PC run Setup-EduRAG.bat once, then Start-EduRAG.bat. Stop with Stop-EduRAG.bat.",
            "Keep port 4747. Do not bind 8080 or 3636. Firewall: inbound TCP 4747, Private profile only.",
            "Nothing leaves the LAN. Do not point config at a cloud API.",
        ],
    }


def format_report(result: dict[str, Any]) -> str:
    lines = ["PACKAGE CHECK", "============="]
    for item in result.get("checks") or []:
        mark = "OK" if item.get("ok") else "FAIL"
        detail = item.get("detail") or ""
        lines.append(f"  [{mark}] {item.get('name')}: {detail}".rstrip(": "))
    for warn in result.get("warnings") or []:
        lines.append(f"  [WARN] {warn}")
    lines.append("")
    if result.get("ok"):
        lines.append("Ready to copy to a second institution PC.")
    else:
        lines.append("Fix FAIL items before packaging for another site.")
    lines.append("")
    lines.append("Copy notes:")
    for note in result.get("copy") or []:
        lines.append(f"  - {note}")
    return "\n".join(lines)
