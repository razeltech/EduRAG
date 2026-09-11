"""EasyOCR wrapper. CPU only, no downloads, native-text callers decide when to use it."""
from __future__ import annotations

import io
import logging
import threading
from pathlib import Path

from app.config_load import load_config

logger = logging.getLogger(__name__)

# EasyOCR recognition weight filename -> language code
_REC_MODELS = {
    "english_g2.pth": "en",
    "latin_g2.pth": "en",
    "devanagari.pth": "hi",
    "chinese.pth": "ch_sim",
    "chinese_sim.pth": "ch_sim",
    "japanese.pth": "ja",
    "korean.pth": "ko",
    "ta.pth": "ta",
    "te.pth": "te",
    "kn.pth": "kn",
    "cyrillic.pth": "ru",
}

_SPARSE_CHAR_THRESHOLD = 40
_reader = None
_reader_error: str | None = None
_lock = threading.Lock()
_langs: list[str] = []


def sparse_text_threshold() -> int:
    return _SPARSE_CHAR_THRESHOLD


def is_sparse(text: str) -> bool:
    alnum = sum(1 for ch in text if ch.isalnum())
    return alnum < _SPARSE_CHAR_THRESHOLD


def model_dir() -> Path | None:
    from app.config_load import ROOT

    cfg = load_config()
    candidates = [
        ROOT / "models" / "ocr",
        Path((cfg.get("ocr") or {}).get("path") or ""),
        Path.home() / ".EasyOCR" / "model",
    ]
    scored: list[tuple[int, Path]] = []
    for folder in candidates:
        if not folder or not folder.is_dir():
            continue
        files = {p.name for p in folder.iterdir() if p.is_file()}
        score = 0
        if "craft_mlt_25k.pth" in files:
            score += 2
        if "english_g2.pth" in files or "latin_g2.pth" in files:
            score += 4
        if "devanagari.pth" in files:
            score += 1
        if score:
            scored.append((score, folder))
    if not scored:
        fallback = Path.home() / ".EasyOCR" / "model"
        return fallback if fallback.is_dir() else None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def available_languages(directory: Path | None = None) -> list[str]:
    folder = directory or model_dir()
    if folder is None:
        return []
    langs: list[str] = []
    for name, lang in _REC_MODELS.items():
        if (folder / name).is_file() and lang not in langs:
            langs.append(lang)
    return langs


def capability_note() -> str | None:
    folder = model_dir()
    if folder is None:
        return "OCR model directory not found."
    langs = available_languages(folder)
    has_detector = (folder / "craft_mlt_25k.pth").is_file()
    if not has_detector:
        return f"EasyOCR detector (craft_mlt_25k.pth) missing in {folder}."
    if not langs:
        return f"No EasyOCR recognition weights in {folder}."
    if "en" not in langs:
        return (
            "EasyOCR has Devanagari/Hindi weights only — english_g2.pth is not on disk. "
            "Scanned English pages will OCR poorly until that file is added."
        )
    return None


def _get_reader():
    global _reader, _reader_error, _langs
    if _reader is not None:
        return _reader
    if _reader_error:
        return None
    with _lock:
        if _reader is not None:
            return _reader
        if _reader_error:
            return None
        folder = model_dir()
        langs = available_languages(folder)
        if "en" in langs:
            langs = ["en"] + [x for x in langs if x != "en"]
        if folder is None or not langs:
            _reader_error = capability_note() or "EasyOCR weights missing."
            logger.warning(_reader_error)
            return None
        try:
            import easyocr  # noqa: WPS433 — optional heavy import
        except ImportError:
            _reader_error = "easyocr is not installed."
            logger.warning(_reader_error)
            return None
        try:
            logger.info("Loading EasyOCR on CPU (%s) from %s", ",".join(langs), folder)
            _reader = easyocr.Reader(
                langs,
                gpu=False,
                download_enabled=False,
                model_storage_directory=str(folder),
            )
            _langs = langs
        except Exception as exc:  # pragma: no cover - hardware/model specific
            _reader_error = f"EasyOCR failed to load: {exc}"
            logger.warning(_reader_error)
            _reader = None
        return _reader


def ocr_image_bytes(data: bytes) -> str:
    reader = _get_reader()
    if reader is None:
        return ""
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return ""
    # Cap huge scans so CPU OCR doesn't balloon RAM.
    max_side = 2400
    w, h = image.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)))
    try:
        rows = reader.readtext(image, paragraph=True, detail=1)
    except Exception as exc:
        logger.warning("OCR read failed: %s", exc)
        return ""
    texts: list[str] = []
    for row in rows:
        if len(row) >= 2:
            texts.append(str(row[1]).strip())
    return "\n".join(t for t in texts if t)


def ocr_image_path(path: Path) -> str:
    return ocr_image_bytes(path.read_bytes())
