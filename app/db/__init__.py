from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.config_load import ROOT, load_config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_schema_sql() -> str:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "app" / "db" / "schema.sql")
        candidates.append(Path(meipass) / "schema.sql")
    candidates.append(SCHEMA_PATH)
    candidates.append(ROOT / "app" / "db" / "schema.sql")
    for p in candidates:
        if p and p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass
    return SCHEMA_PATH.read_text(encoding="utf-8")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return uuid.uuid4().hex


def db_path() -> Path:
    env = os.environ.get("EDURAG_DB")
    if env:
        path = Path(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    cfg = load_config()
    raw = (cfg.get("database") or {}).get("path")
    path = Path(raw) if raw else ROOT / "data" / "edurag.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    own = conn is None
    conn = conn or connect()
    conn.executescript(get_schema_sql())
    _migrate(conn)
    _ensure_institution(conn)
    conn.commit()
    if own:
        return conn
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(courses)").fetchall()}
    if "age_band" not in cols:
        conn.execute(
            "ALTER TABLE courses ADD COLUMN age_band TEXT NOT NULL DEFAULT 'adult'"
        )


def _ensure_institution(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT id FROM institutions LIMIT 1").fetchone()
    if row:
        return row["id"]
    iid = new_id()
    conn.execute(
        "INSERT INTO institutions (id, name, created_at) VALUES (?, ?, ?)",
        (iid, "Local Institution", utcnow()),
    )
    return iid


def default_institution_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT id FROM institutions LIMIT 1").fetchone()
    if row:
        return row["id"]
    return _ensure_institution(conn)


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def pack_vector(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def unpack_vector(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32).reshape(dim)
