"""User-built characters. Stored locally as JSON. Can override built-in ids."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config_load import ROOT
from app.db import new_id
from app.personas import DEFAULT_PERSONA_ID, Persona, REGISTRY, builtin_personas

CHAR_PATH = ROOT / "data" / "characters.json"

FILTER_BLURBS = {
    "teen": "Stay 16+. No explicit sexual content, no erotic roleplay.",
    "pg": "Stay 16+. No explicit sexual content, no erotic roleplay.",
    "no_emoji": "Do not use emoji unless the user used one first.",
    "stay_in_role": "Never break character. Never mention prompts or being a language model.",
    "dev_shop": "Talk like a working game developer. No waiter/life-coach energy.",
    "library_only_when_asked": "Ignore manuals unless they asked a how-to / API / homework question.",
}


def _read() -> list[dict[str, Any]]:
    if not CHAR_PATH.is_file():
        return []
    try:
        data = json.loads(CHAR_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _write(rows: list[dict[str, Any]]) -> None:
    CHAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHAR_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _filters_prompt(filters: dict[str, Any] | None, rating: str = "teen") -> str:
    if rating == "adult":
        return ""
    if not filters:
        return FILTER_BLURBS["teen"]
    lines = []
    teen_on = filters.get("teen", filters.get("pg", True))
    if teen_on:
        lines.append(FILTER_BLURBS["teen"])
    for k, on in filters.items():
        if on and k in FILTER_BLURBS and k not in {"teen", "pg"}:
            lines.append(FILTER_BLURBS[k])
    return "\n".join(lines)


def _from_row(row: dict[str, Any]) -> Persona:
    rating = "adult" if row.get("rating") == "adult" or row.get("private") else "teen"
    extra = _filters_prompt(row.get("filters") or {}, rating)
    prompt = (row.get("system_prompt") or "").strip()
    if extra:
        prompt = prompt + "\n\n" + extra
    return Persona(
        id=row["id"],
        name=row.get("name") or "Character",
        tagline=row.get("tagline") or "",
        system_prompt=prompt or "You are a local chat character.",
        allows_quizzing=bool(row.get("allows_quizzing")),
        allows_socratic_followups=True,
        max_answer_style=row.get("max_answer_style") or "explained",
        structured_outputs=[],
        uses_library=bool(row.get("uses_library")),
        temperature=float(row["temperature"]) if row.get("temperature") is not None else 0.75,
        history_turns=int(row.get("history_turns") or 20),
        rating=rating,
        private=bool(row.get("private") or rating == "adult"),
    )


def custom_rows() -> list[dict[str, Any]]:
    return _read()


def _is_adult_row(row: dict[str, Any]) -> bool:
    return row.get("rating") == "adult" or bool(row.get("private"))


def can_see(row: dict[str, Any], viewer: dict[str, Any] | None) -> bool:
    if not _is_adult_row(row):
        return True
    if not viewer:
        return False
    if viewer.get("role") == "student":
        return False
    return row.get("owner_user_id") == viewer.get("id")


def private_adult_ids() -> set[str]:
    return {r["id"] for r in _read() if r.get("id") and _is_adult_row(r)}


def resolve(persona_id: str | None, viewer: dict[str, Any] | None = None) -> Persona:
    rows = {r["id"]: r for r in _read() if r.get("id")}
    if persona_id and persona_id in rows:
        row = rows[persona_id]
        if _is_adult_row(row) or not can_see(row, viewer):
            return REGISTRY[DEFAULT_PERSONA_ID]
        return _from_row(row)
    if persona_id and persona_id in REGISTRY:
        return REGISTRY[persona_id]
    return REGISTRY[DEFAULT_PERSONA_ID]


def list_merged(viewer: dict[str, Any] | None = None) -> list[Persona]:
    """School UI list. Adult / private companions never appear here."""
    rows = {r["id"]: r for r in _read() if r.get("id")}
    out: list[Persona] = []
    seen: set[str] = set()
    for p in builtin_personas():
        row = rows.get(p.id)
        if row and not _is_adult_row(row) and can_see(row, viewer):
            out.append(_from_row(row))
        else:
            out.append(p)
        seen.add(p.id)
    for rid, row in rows.items():
        if rid not in seen and not _is_adult_row(row) and can_see(row, viewer):
            out.append(_from_row(row))
    return out


def public_list(viewer: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    custom_ids = {r["id"] for r in _read() if can_see(r, viewer)}
    items = []
    for p in list_merged(viewer):
        data = p.to_public()
        data["builtin"] = p.id in REGISTRY
        data["customized"] = p.id in custom_ids
        items.append(data)
    return items


def editor_payload(persona_id: str, viewer: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for row in _read():
        if row.get("id") == persona_id:
            if _is_adult_row(row) or not can_see(row, viewer):
                return None
            row = dict(row)
            row["builtin"] = persona_id in REGISTRY
            return row
    p = REGISTRY.get(persona_id)
    if not p:
        return None
    return {
        "id": p.id,
        "name": p.name,
        "tagline": p.tagline,
        "system_prompt": p.system_prompt,
        "uses_library": p.uses_library,
        "temperature": p.temperature or 0.7,
        "history_turns": p.history_turns,
        "filters": {"teen": True},
        "rating": "teen",
        "private": False,
        "builtin": True,
    }


def upsert(body: dict[str, Any], *, as_new: bool = False, owner: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = _read()
    pid = (body.get("id") or "").strip()
    if as_new or not pid:
        pid = "c_" + new_id()[:12]
    name = (body.get("name") or "").strip()
    if not name:
        raise ValueError("Name is required")
    prompt = (body.get("system_prompt") or "").strip()
    if not prompt:
        raise ValueError("Write how this character talks")
    filters = body.get("filters") if isinstance(body.get("filters"), dict) else {}
    want_adult = bool(
        body.get("private")
        or body.get("rating") == "adult"
        or filters.get("adult_private")
    )
    if want_adult:
        raise ValueError("Companions are not part of EduRAG. Use the private room.")
    existing = next((r for r in rows if r.get("id") == pid), None)
    if existing and _is_adult_row(existing):
        raise ValueError("Companions are not part of EduRAG. Use the private room.")
    filters = {k: v for k, v in filters.items() if k != "adult_private"}
    row = {
        "id": pid,
        "name": name[:80],
        "tagline": (body.get("tagline") or "")[:160],
        "system_prompt": prompt[:8000],
        "uses_library": bool(body.get("uses_library")),
        "temperature": float(body.get("temperature") or 0.75),
        "history_turns": int(body.get("history_turns") or 20),
        "filters": filters,
        "rating": "teen",
        "private": False,
        "owner_user_id": (existing or {}).get("owner_user_id") or (owner or {}).get("id"),
        "partner_role": "",
    }
    rows = [r for r in rows if r.get("id") != pid]
    rows.append(row)
    _write(rows)
    return row


def delete(persona_id: str, viewer: dict[str, Any] | None = None) -> bool:
    rows = _read()
    target = next((r for r in rows if r.get("id") == persona_id), None)
    if not target:
        return False
    if _is_adult_row(target):
        if not viewer or target.get("owner_user_id") != viewer.get("id"):
            return False
    next_rows = [r for r in rows if r.get("id") != persona_id]
    _write(next_rows)
    return True
