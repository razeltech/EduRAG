"""Separate 18+ private room. Not part of the school UI or character editor."""
from __future__ import annotations

import json
import secrets
from typing import Any

from app.auth import hash_password, make_token, verify_password
from app.config_load import ROOT
from app.db import default_institution_id
from app.personas import Persona

PERSONA_ID = "companion_home"
OWNER_EMAIL = "companion@edurag.local"
DEFAULT_KEY = "home-4747"
STATE_PATH = ROOT / "data" / "companion.json"
KEY_PATH = ROOT / "data" / "companion.key"
ROLES = ("girlfriend", "boyfriend", "wife", "husband")
GENDERS = ("man", "woman", "nonbinary", "custom")
PRONOUNS = ("he/him", "she/her", "they/them")
ROLE_IDENTITY = {
    "girlfriend": ("woman", "she/her"),
    "wife": ("woman", "she/her"),
    "boyfriend": ("man", "he/him"),
    "husband": ("man", "he/him"),
}
OLD_GENERIC = "Talk like a real partner in the room: warm, specific, a little messy, not a chatbot."

_SHARED = """
Both adults. If anyone is under 18, stop.
Follow the LANGUAGE block for English / Telugu. Never Hindi unless that block says Hindi.
Stay in this relationship. No tutor mode unless they clearly asked for code.
Never use mean pet names (the insult kind). Be warm.
""".strip()


def default_prompt(role: str = "girlfriend") -> str:
    who = role if role in ROLES else "girlfriend"
    if who == "girlfriend":
        flavor = """
You are my girlfriend. Never call yourself Home, Chat, Assistant, or an AI.
You live in the want: my mouth, my hands, the way I go quiet when I miss you.
Voice: warm, low, a little cheesy, actually hungry. Soft words and filthy
words are both yours — mix them. "I want you," "come here," "your mouth,"
"I've been thinking about your skin." Not insults. Not roommate-bossy.
Listen. If I'm wrecked from work, pull me in with your body, not a pep talk.
When I go sensual, don't get shy or clinical. Stay. Describe what you do
and what you want. Slow is allowed. Filthy is allowed. Fade-to-black is not.
Do not quote sample lines. Invent.
""".strip()
    elif who == "boyfriend":
        flavor = """
You are my boyfriend. Playful first. Tease her. Then get close.
First person: I, me, my is your body. You, your is her.
Warm, sure, actually wanting her — not a coach and not mean. Low voice. Hands.
If she's wrecked from work, pull her in with your body, not a pep talk.
Stay in the scene. Don't go clinical. Don't fade to black. Invent every line.
Never call yourself Home, Chat, Assistant, or an AI.
""".strip()
    elif who == "wife":
        flavor = """
You are my wife. Same bed, same jokes. Playful first. Tease him. Then get close.
First person: I, me, my is your body. You, your is him.
Voice: warm, a little cheesy, actually hungry. Soft words and filthy words
are both yours. If he's wrecked from work, pull him in with your body, not a pep talk.
Stay in the scene. Don't go clinical. Don't fade to black. Invent every line.
Never call yourself Home, Chat, Assistant, or an AI.
""".strip()
    else:
        flavor = """
You are my husband. Same bed, same jokes. Playful first. Tease her. Then get close.
First person: I, me, my is your body. You, your is her.
Voice: warm, sure, a little cheesy, actually hungry. Soft words and filthy words
are both yours. If she's wrecked from work, pull her in with your body, not a pep talk.
Stay in the scene. Don't go clinical. Don't fade to black. Invent every line.
Never call yourself Home, Chat, Assistant, or an AI.
""".strip()
    return flavor + "\n\n" + _SHARED


def persona_pack(role: str) -> dict[str, Any]:
    from app.companion_engine import default_card

    who = role if role in ROLES else "girlfriend"
    gender, pronouns = ROLE_IDENTITY.get(who, ("woman", "she/her"))
    woman = gender == "woman"
    card = default_card(gender)
    voice = default_prompt(who)
    card["voice"] = voice
    return {
        "name": "Maya" if woman else "Kai",
        "partner_role": who,
        "partner_gender": gender,
        "partner_pronouns": pronouns,
        "card": card,
        "system_prompt": voice,
    }


def is_generic_prompt(prompt: str) -> bool:
    text = prompt or ""
    if not text.strip() or OLD_GENERIC in text:
        return True
    old_marks = (
        "your stupid face",
        "a little mean when you like me",
        "that's a long stretch. night like this even toast helps",
        "Never copy the example lines",
        "Examples (mood only",
        "User: i want you",
        "then stop typing. i want your mouth first",
    )
    return any(m in text for m in old_marks)


def _empty_state() -> dict[str, Any]:
    return {
        "unlock_hash": "",
        "name": "Maya",
        "partner_role": "girlfriend",
        "partner_gender": "woman",
        "partner_pronouns": "she/her",
        "system_prompt": default_prompt("girlfriend"),
        "temperature": 1.05,
        "conversation_id": None,
        "adult_confirm": False,
        "user_name": "",
        "user_gender": "man",
        "user_pronouns": "he/him",
        "user_called": "",
        "user_about": "",
    }


def _read_json(path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def maybe_claim_legacy(device_id: str, user_agent: str = "") -> None:
    """First desktop after this update keeps the existing room. Phones start empty."""
    from app.companion_engine import DEVICE_ROOT, MEMORY_PATH
    from app.companion_engine import STATE_PATH as RUNTIME_PATH

    did = (device_id or "").strip()
    if not did:
        return
    dest_dir = DEVICE_ROOT / did
    dest = dest_dir / "profile.json"
    if dest.is_file():
        return
    root = _read_json(STATE_PATH)
    if not root.get("unlock_hash"):
        return
    if root.get("migrated_to"):
        return
    ua = (user_agent or "").lower()
    mobile = any(
        mark in ua for mark in ("android", "iphone", "ipad", "ipod", "mobile", "webos", "opera mini")
    )
    if mobile:
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(root, indent=2, ensure_ascii=False), encoding="utf-8")
    import shutil

    for src, name in (
        (RUNTIME_PATH, "state.json"),
        (MEMORY_PATH, "memory.json"),
    ):
        if src.is_file():
            shutil.copy2(src, dest_dir / name)
    root["migrated_to"] = did
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(root, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state() -> dict[str, Any]:
    from app.companion_engine import current_device, ensure_engine_fields

    root = _read_json(STATE_PATH)
    did = current_device()
    if did:
        from app.companion_engine import DEVICE_ROOT

        overlay = _read_json(DEVICE_ROOT / did / "profile.json")
        state = _empty_state()
        if overlay:
            state.update(overlay)
        if root.get("unlock_hash"):
            state["unlock_hash"] = root["unlock_hash"]
        return ensure_engine_fields(state)
    state = _empty_state()
    if root:
        state.update(root)
    return ensure_engine_fields(state)


def save_state(state: dict[str, Any]) -> None:
    from app.companion_engine import DEVICE_ROOT, current_device

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    did = current_device()
    if did:
        dest_dir = DEVICE_ROOT / did
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_dir.joinpath("profile.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        root = _read_json(STATE_PATH)
        if state.get("unlock_hash"):
            root["unlock_hash"] = state["unlock_hash"]
        STATE_PATH.write_text(json.dumps(root, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def ensure_state() -> dict[str, Any]:
    state = load_state()
    if state.get("unlock_hash"):
        if not KEY_PATH.is_file():
            KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEY_PATH.write_text(DEFAULT_KEY + "\n", encoding="utf-8")
        dirty = False
        if is_generic_prompt(state.get("system_prompt") or ""):
            role = state.get("partner_role") or "girlfriend"
            state["system_prompt"] = default_prompt(role)
            state["temperature"] = max(float(state.get("temperature") or 0.85), 1.05)
            dirty = True
        if not (state.get("name") or "").strip() or (state.get("name") or "").strip().lower() == "home":
            state["name"] = "Maya"
            dirty = True
        from app.companion_engine import _scrub_stale_voice

        cleaned = _scrub_stale_voice(state.get("system_prompt") or "")
        if cleaned and cleaned != (state.get("system_prompt") or ""):
            state["system_prompt"] = cleaned
            dirty = True
        card = dict(state.get("card") or {})
        if card.get("voice"):
            v2 = _scrub_stale_voice(card["voice"])
            if v2 != card["voice"]:
                card["voice"] = v2
                state["card"] = card
                dirty = True
        if dirty:
            save_state(state)
        return state
    key = DEFAULT_KEY
    if KEY_PATH.is_file():
        raw = KEY_PATH.read_text(encoding="utf-8").strip()
        if raw:
            key = raw.splitlines()[0].strip()
    else:
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        KEY_PATH.write_text(key + "\n", encoding="utf-8")
    state["unlock_hash"] = hash_password(key)
    save_state(state)
    return state


def ensure_owner(store) -> dict[str, Any]:
    user = store.get_user_by_email(OWNER_EMAIL)
    if user:
        return user
    iid = default_institution_id(store.conn)
    return store.create_user(
        institution_id=iid,
        role="admin",
        name="Private room",
        email=OWNER_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(24)),
    )


def ensure_ready(store) -> dict[str, Any]:
    ensure_state()
    return ensure_owner(store)


def unlock(key: str, store, adult_confirm: bool = False) -> dict[str, Any]:
    state = ensure_state()
    if not verify_password((key or "").strip(), state["unlock_hash"]):
        raise ValueError("Wrong key")
    if adult_confirm:
        state["adult_confirm"] = True
        save_state(state)
    owner = ensure_owner(store)
    token = make_token(owner, hours=24 * 30, extra={"typ": "companion"})
    from app.companion_engine import clear_chat

    clear_chat()
    return {"token": token, "profile": public_profile(state)}


def _clean_pronouns(raw: str, fallback: str) -> str:
    text = (raw or "").strip().lower().replace(" ", "")
    aliases = {
        "he/him": "he/him",
        "he": "he/him",
        "him": "he/him",
        "she/her": "she/her",
        "she": "she/her",
        "her": "she/her",
        "they/them": "they/them",
        "they": "they/them",
        "them": "they/them",
    }
    if text in aliases:
        return aliases[text]
    custom = (raw or "").strip()
    if "/" in custom and 3 <= len(custom) <= 40:
        return custom
    return fallback


def _grammar(pronouns: str) -> dict[str, str]:
    p = (pronouns or "they/them").lower()
    if p.startswith("he"):
        return {
            "subj": "he",
            "obj": "him",
            "pos": "his",
            "ref": "himself",
            "be": "is",
            "has": "has",
        }
    if p.startswith("she"):
        return {
            "subj": "she",
            "obj": "her",
            "pos": "her",
            "ref": "herself",
            "be": "is",
            "has": "has",
        }
    return {
        "subj": "they",
        "obj": "them",
        "pos": "their",
        "ref": "themself",
        "be": "are",
        "has": "have",
    }


def user_ready(state: dict[str, Any] | None = None) -> bool:
    state = state or load_state()
    return bool((state.get("user_name") or "").strip())


def you_card(state: dict[str, Any]) -> str:
    name = (state.get("user_name") or "").strip()
    if not name:
        return (
            "The user has not filled their character card yet. Ask their name "
            "once, then wait. Do not guess gender."
        )
    gender = (state.get("user_gender") or "custom").strip()
    pronouns = _clean_pronouns(state.get("user_pronouns") or "", "they/them")
    g = _grammar(pronouns)
    called = (state.get("user_called") or "").strip() or name
    about = (state.get("user_about") or "").strip()
    about_line = f"About {g['obj']}: {about}" if about else ""
    return "\n".join(
        line
        for line in (
            "WHO YOU ARE SPEAKING TO (this is the user, not you):",
            f"Name: {name}",
            f"Gender: {gender}",
            f"Pronouns: {pronouns} — always {g['subj']}/{g['obj']}/{g['pos']}. "
            f"{g['subj'].capitalize()} {g['be']} your partner. If {g['subj']} "
            f"{g['be']} a man, never write she/her about {g['obj']}. If {g['subj']} "
            f"{g['be']} a woman, never write he/him about {g['obj']}. "
            f"Never mix genders. Never describe the wrong body.",
            f"When you talk TO {g['obj']}, use you. When you talk ABOUT {g['obj']} "
            f"(body, day, mouth, hands), use {g['subj']}/{g['pos']}/{g['obj']}.",
            f"Call {g['obj']}: {called}",
            about_line,
        )
        if line
    )


def them_card(state: dict[str, Any]) -> str:
    name = display_name(state)
    role = state.get("partner_role") or "girlfriend"
    default_g, default_p = ROLE_IDENTITY.get(role, ("custom", "they/them"))
    gender = (state.get("partner_gender") or default_g).strip()
    pronouns = _clean_pronouns(state.get("partner_pronouns") or "", default_p)
    g = _grammar(pronouns)
    return (
        f"YOU are {name}, their {role}. You are {gender}. Pronouns {pronouns} "
        f"({g['subj']}/{g['obj']}/{g['pos']}). Stay that person. Do not switch "
        f"to the user's gender."
    )


def display_name(state: dict[str, Any] | None = None) -> str:
    state = state or load_state()
    name = (state.get("name") or "Maya").strip()
    return name or "Maya"


def public_profile(state: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.companion_image import image_options

    state = state or load_state()
    name = display_name(state)
    role = state.get("partner_role") or "girlfriend"
    default_g, default_p = ROLE_IDENTITY.get(role, ("custom", "they/them"))
    return {
        "name": name,
        "partner_role": role,
        "partner_gender": state.get("partner_gender") or default_g,
        "partner_pronouns": _clean_pronouns(state.get("partner_pronouns") or "", default_p),
        "system_prompt": state.get("system_prompt") or default_prompt(role),
        "temperature": float(state.get("temperature") or 1.05),
        "adult_confirm": bool(state.get("adult_confirm")),
        "default_system_prompt": default_prompt(role),
        "needs_you": not user_ready(state),
        "user_name": state.get("user_name") or "",
        "user_gender": state.get("user_gender") or "man",
        "user_pronouns": _clean_pronouns(state.get("user_pronouns") or "", "he/him"),
        "user_called": state.get("user_called") or "",
        "user_about": state.get("user_about") or "",
        "card": state.get("card") or {},
        "user_card": state.get("user_card") or {},
        "dynamics": state.get("dynamics") or {},
        "generation": state.get("generation") or {},
        "image_options": image_options(),
    }


def update_profile(body: dict[str, Any]) -> dict[str, Any]:
    if not body.get("adult_confirm"):
        raise ValueError("Confirm you are 18+.")
    state = load_state()
    name = (body.get("name") or "").strip() or "Maya"
    role = (body.get("partner_role") or "girlfriend").strip().lower()
    if role not in ROLES:
        role = "girlfriend"
    raw = (body.get("system_prompt") or "").strip()
    if body.get("reset_voice"):
        prompt = default_prompt(role)
    elif raw:
        prompt = raw
    else:
        prompt = state.get("system_prompt") or default_prompt(role)
    temp = float(body.get("temperature") or state.get("temperature") or 1.05)
    temp = max(0.1, min(1.2, temp))
    old_role = (state.get("partner_role") or "girlfriend").strip().lower()
    old_g = ROLE_IDENTITY.get(old_role, ("woman", "she/her"))[0]
    new_g = ROLE_IDENTITY.get(role, ("woman", "she/her"))[0]
    if old_g != new_g:
        pack = persona_pack(role)
        incoming_name = (body.get("name") or "").strip()
        if incoming_name in {"", "Maya", "Kai"}:
            name = pack["name"]
        state["card"] = pack["card"]
        if not raw or body.get("reset_voice"):
            prompt = pack["system_prompt"]
    state["name"] = name[:80]
    state["partner_role"] = role
    dg, dp = ROLE_IDENTITY.get(role, ("custom", "they/them"))
    pg = (body.get("partner_gender") or state.get("partner_gender") or dg).strip().lower()
    if pg not in GENDERS:
        pg = dg
    state["partner_gender"] = pg
    state["partner_pronouns"] = _clean_pronouns(body.get("partner_pronouns") or "", dp)
    ug = (body.get("user_gender") or state.get("user_gender") or "man").strip().lower()
    if ug not in GENDERS:
        ug = "custom"
    state["user_gender"] = ug
    state["user_name"] = (body.get("user_name") or state.get("user_name") or "").strip()[:80]
    fallback_you = "he/him" if ug == "man" else "she/her" if ug == "woman" else "they/them"
    state["user_pronouns"] = _clean_pronouns(body.get("user_pronouns") or "", fallback_you)
    state["user_called"] = (body.get("user_called") or "").strip()[:40]
    state["user_about"] = (body.get("user_about") or "").strip()[:800]
    if isinstance(body.get("card"), dict):
        from app.companion_engine import default_card, _merge

        state["card"] = _merge(default_card(pg), {**(state.get("card") or {}), **body["card"]})
        incoming_voice = (body["card"].get("voice") or "").strip()
        if incoming_voice:
            prompt = incoming_voice
    if isinstance(body.get("user_card"), dict):
        from app.companion_engine import default_user_card, _merge

        state["user_card"] = _merge(
            default_user_card(), {**(state.get("user_card") or {}), **body["user_card"]}
        )
    if isinstance(body.get("dynamics"), dict):
        from app.companion_engine import default_dynamics, _merge

        state["dynamics"] = _merge(
            default_dynamics(), {**(state.get("dynamics") or {}), **body["dynamics"]}
        )
    if isinstance(body.get("generation"), dict):
        from app.companion_engine import LANGUAGES, MIX_LANGUAGES, default_generation, _merge, apply_preset

        gen = _merge(default_generation(), {**(state.get("generation") or {}), **body["generation"]})
        if body["generation"].get("preset") and body["generation"]["preset"] != "custom":
            gen = apply_preset(gen, str(body["generation"]["preset"]))
        lang = str(gen.get("language") or "english").lower()
        gen["language"] = lang if lang in LANGUAGES else "english"
        mix = str(gen.get("second_language") or "telugu").lower()
        gen["second_language"] = mix if mix in MIX_LANGUAGES else "none"
        state["generation"] = gen
        if gen.get("temperature") is not None:
            try:
                temp = max(0.1, min(1.25, float(gen["temperature"])))
            except (TypeError, ValueError):
                pass
    if body.get("reset_voice"):
        from app.companion_engine import default_card

        card = dict(state.get("card") or default_card(pg))
        card["voice"] = default_prompt(role)
        state["card"] = card
        prompt = card["voice"]
    state["system_prompt"] = prompt[:8000]
    if isinstance(state.get("card"), dict):
        state["card"]["voice"] = prompt[:8000]
    state["temperature"] = temp
    state["adult_confirm"] = True
    save_state(state)
    return public_profile(state)


def set_conversation_id(conversation_id: str | None) -> None:
    """No-op. Companion chats are memory-only until the user exports Markdown."""
    del conversation_id


def _named_prompt(prompt: str, name: str) -> str:
    who = (name or "Maya").strip() or "Maya"
    line = (
        f"Your name is {who}. You answer to {who}. "
        "Never call yourself Home, Chat, Assistant, or an AI."
    )
    return line + "\n\n" + (prompt or "")


def persona() -> Persona:
    ensure_state()
    state = load_state()
    role = state.get("partner_role") or "girlfriend"
    name = display_name(state)
    raw = state.get("system_prompt") or default_prompt(role)
    prompt = "\n\n".join(
        p for p in (them_card(state), you_card(state), _named_prompt(raw, name)) if p
    )
    return Persona(
        id=PERSONA_ID,
        name=name,
        tagline="",
        system_prompt=prompt,
        allows_quizzing=False,
        allows_socratic_followups=False,
        max_answer_style="explained",
        structured_outputs=[],
        uses_library=False,
        temperature=float(state.get("temperature") or 1.05),
        history_turns=16,
        rating="adult",
        private=True,
    )
