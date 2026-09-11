"""Load config.yaml written by model-discovery."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or CONFIG_PATH
    if not cfg_path.is_file():
        return {}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data
