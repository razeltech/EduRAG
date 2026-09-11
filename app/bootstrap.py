"""First-boot jobs: demo users, English OCR weights, Ollama model."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlopen

from app.config_load import ROOT, load_config
from app.db import default_institution_id, init_db
from app.db.store import Store

DEMO_ACCOUNTS = [
    {
        "name": "Admin",
        "email": "admin@edurag.local",
        "password": "admin123",
        "role": "admin",
        "label": "Admin",
    },
    {
        "name": "Teacher",
        "email": "teacher@edurag.local",
        "password": "teacher123",
        "role": "teacher",
        "label": "Teacher",
    },
    {
        "name": "Student",
        "email": "student@edurag.local",
        "password": "student123",
        "role": "student",
        "label": "Student",
    },
]

ENGLISH_OCR_ZIP = (
    "https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip"
)


def seed_demo_users(store: Store | None = None) -> list[str]:
    """Create the three LAN seats, or reset their passwords if they already exist."""
    from app.auth import hash_password

    store = store or Store(init_db())
    iid = default_institution_id(store.conn)
    created: list[str] = []
    for acc in DEMO_ACCOUNTS:
        hashed = hash_password(acc["password"])
        existing = store.get_user_by_email(acc["email"])
        if existing:
            store.set_password_hash(existing["id"], hashed)
            created.append(acc["email"] + " (password reset)")
            continue
        store.create_user(
            institution_id=iid,
            role=acc["role"],
            name=acc["name"],
            email=acc["email"],
            password_hash=hashed,
        )
        created.append(acc["email"])
    return created


def public_demo_accounts() -> list[dict[str, str]]:
    return [
        {
            "label": a["label"],
            "email": a["email"],
            "password": a["password"],
            "role": a["role"],
        }
        for a in DEMO_ACCOUNTS
    ]


def _ocr_dirs() -> list[Path]:
    cfg = load_config()
    dirs = [ROOT / "models" / "ocr", Path.home() / ".EasyOCR" / "model"]
    raw = (cfg.get("ocr") or {}).get("path")
    if raw:
        dirs.insert(0, Path(raw))
    unique: list[Path] = []
    for d in dirs:
        if d not in unique:
            unique.append(d)
    return unique


def ensure_english_ocr() -> Path | None:
    """Put english_g2.pth next to the detector so scanned English pages work."""
    dest_dirs = _ocr_dirs()
    existing = None
    for folder in dest_dirs:
        candidate = folder / "english_g2.pth"
        if candidate.is_file() and candidate.stat().st_size > 1_000_000:
            existing = candidate
            break
    if existing:
        _mirror_ocr(existing)
        return existing

    folder = ROOT / "models" / "ocr"
    folder.mkdir(parents=True, exist_ok=True)
    zip_path = folder / "english_g2.zip"
    print("Downloading English OCR weights (english_g2.pth)…")
    try:
        with urlopen(ENGLISH_OCR_ZIP, timeout=120) as resp, zip_path.open("wb") as out:
            shutil.copyfileobj(resp, out)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(folder)
        zip_path.unlink(missing_ok=True)
    except Exception as exc:
        print(f"English OCR download failed: {exc}")
        return None

    pth = folder / "english_g2.pth"
    if not pth.is_file():
        found = next(folder.rglob("english_g2.pth"), None)
        if found:
            shutil.copy2(found, pth)
    if pth.is_file():
        _mirror_ocr(pth)
        print(f"English OCR ready: {pth}")
        return pth
    print("english_g2.pth not found after download.")
    return None


def _mirror_ocr(english: Path) -> None:
    home = Path.home() / ".EasyOCR" / "model"
    home.mkdir(parents=True, exist_ok=True)
    bundled = ROOT / "models" / "ocr"
    bundled.mkdir(parents=True, exist_ok=True)
    for dest in {home, bundled}:
        target = dest / "english_g2.pth"
        if target.resolve() != english.resolve() and not target.is_file():
            try:
                shutil.copy2(english, target)
            except OSError:
                pass
        for name in ("craft_mlt_25k.pth", "devanagari.pth"):
            src = None
            for folder in (english.parent, home, bundled):
                cand = folder / name
                if cand.is_file():
                    src = cand
                    break
            if src is None:
                continue
            out = dest / name
            if not out.is_file():
                try:
                    shutil.copy2(src, out)
                except OSError:
                    pass


def ensure_ollama_model() -> str:
    cfg = load_config()
    model = (cfg.get("llm") or {}).get("model") or "qwen2.5:7b-instruct"
    ollama = shutil.which("ollama")
    if not ollama:
        return "Ollama not on PATH yet."
    listed = subprocess.run(
        [ollama, "list"], capture_output=True, text=True, timeout=30, check=False
    )
    if listed.returncode == 0 and model.split(":")[0] in listed.stdout and model in listed.stdout:
        return f"Ollama model already present: {model}"
    print(f"Pulling Ollama model {model} (first time can take several minutes)…")
    pull = subprocess.run([ollama, "pull", model], check=False)
    if pull.returncode != 0:
        return f"ollama pull {model} failed (exit {pull.returncode})"
    return f"Ollama model ready: {model}"


def run_setup() -> dict[str, str]:
    conn = init_db()
    store = Store(conn)
    created = seed_demo_users(store)
    ocr = ensure_english_ocr()
    llm = ensure_ollama_model()
    return {
        "demo_users": ", ".join(created) if created else "already seeded",
        "english_ocr": str(ocr) if ocr else "MISSING",
        "llm": llm,
    }
