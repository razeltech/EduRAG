"""Browse folders on the server PC — for indexing local Unity/Unreal/docs trees."""
from __future__ import annotations

import os
import string
from pathlib import Path

from app.ingest.scanner import is_supported

SKIP_DIR_NAMES = {
    "$recycle.bin",
    "system volume information",
    "recovery",
    "config.msi",
    "documents and settings",
}


def _roots() -> list[dict]:
    entries: list[dict] = []
    home = Path.home()
    if home.exists():
        entries.append({"name": "Home", "path": str(home), "kind": "dir", "hint": ""})
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            try:
                if drive.exists():
                    entries.append(
                        {
                            "name": f"{letter}:",
                            "path": str(drive),
                            "kind": "dir",
                            "hint": "",
                        }
                    )
            except OSError:
                continue
    else:
        entries.append({"name": "/", "path": "/", "kind": "dir", "hint": ""})
    return entries


def _parent(path: Path) -> str | None:
    parent = path.parent
    if parent == path:
        return None
    return str(parent)


def _hint(path: Path) -> str:
    files = 0
    folders = 0
    try:
        for item in path.iterdir():
            try:
                if item.is_dir():
                    folders += 1
                elif item.is_file() and is_supported(item, include_images=False):
                    files += 1
            except OSError:
                continue
    except OSError:
        return ""
    bits = []
    if folders:
        bits.append(f"{folders} folders")
    if files:
        bits.append(f"{files} docs")
    return ", ".join(bits)


def list_folder(path: str | None) -> dict:
    if not path:
        return {"path": "", "parent": None, "entries": _roots()}
    target = Path(path).expanduser()
    try:
        target = target.resolve()
    except OSError as exc:
        raise FileNotFoundError(str(exc)) from exc
    if not target.is_dir():
        raise FileNotFoundError(str(target))

    entries: list[dict] = []
    try:
        children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        raise PermissionError(str(exc)) from exc

    for item in children:
        name = item.name
        if name.startswith(".") and name not in {".", ".."}:
            continue
        if name.lower() in SKIP_DIR_NAMES:
            continue
        try:
            if not item.is_dir():
                continue
        except OSError:
            continue
        entries.append(
            {
                "name": name,
                "path": str(item),
                "kind": "dir",
                "hint": _hint(item) if len(entries) < 40 else "",
            }
        )
        if len(entries) >= 400:
            break

    return {
        "path": str(target),
        "parent": _parent(target),
        "entries": entries,
        "hint": _hint(target),
    }
