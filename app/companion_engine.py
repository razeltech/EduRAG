"""Companion runtime: cards, state, memory, context, inference.

School RAG / personas / safety stay untouched. This module is only used by
the private room.
"""
from __future__ import annotations

import contextvars
import json
import re
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.config_load import ROOT
from app.llm import chat_stream

STATE_PATH = ROOT / "data" / "companion_state.json"
MEMORY_PATH = ROOT / "data" / "companion_memory.json"
CHAT_PATH = ROOT / "data" / "companion_chat.json"
DEVICE_ROOT = ROOT / "data" / "companion_devices"
_CHAT_FILE_LOCK = threading.Lock()
_LIVE_CHAT: dict[str, list[dict[str, Any]]] = {}
_LIVE_SCENE: dict[str, dict[str, Any]] = {}
_DEVICE: contextvars.ContextVar[str] = contextvars.ContextVar("companion_device", default="")
CHAT_KEEP = 36
_SCENE_KEYS = frozenset(
    {
        "rewrite",
        "last_picture",
        "last_offer_ts",
        "last_offer_turn",
        "action",
        "location",
        "outfit",
        "expression",
        "camera",
        "kind",
        "user_note",
        "lighting",
        "mood",
        "time",
        "style",
        "frame",
        "drop",
        "literal",
    }
)


def current_device() -> str:
    return _DEVICE.get() or ""


def set_device(raw: str) -> str:
    did = re.sub(r"[^a-zA-Z0-9_-]", "", raw or "")[:80]
    _DEVICE.set(did)
    return did


def bind_device(raw: str, user_agent: str = "") -> str:
    did = set_device(raw)
    if did:
        from app.companion import maybe_claim_legacy

        maybe_claim_legacy(did, user_agent)
    return did


def _device_dir() -> Path | None:
    did = current_device()
    if not did:
        return None
    path = DEVICE_ROOT / did
    path.mkdir(parents=True, exist_ok=True)
    return path


def _runtime_file() -> Path:
    folder = _device_dir()
    return folder / "state.json" if folder else STATE_PATH


def _memory_file() -> Path:
    folder = _device_dir()
    return folder / "memory.json" if folder else MEMORY_PATH


def _chat_slot() -> str:
    return current_device() or "_"

STYLES = ("chat", "roleplay", "story", "minimal", "descriptive")
LANGUAGES = ("english", "telugu", "tinglish", "hindi", "match")
MIX_LANGUAGES = ("none", "telugu", "tinglish")
PRESETS = {
    "balanced": {
        "temperature": 0.88,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.14,
        "num_predict": 768,
    },
    "creative": {
        "temperature": 1.08,
        "top_p": 0.95,
        "top_k": 60,
        "repeat_penalty": 1.08,
        "num_predict": 900,
    },
    "roleplay": {
        "temperature": 1.0,
        "top_p": 0.92,
        "top_k": 50,
        "repeat_penalty": 1.16,
        "num_predict": 1024,
    },
    "character": {
        "temperature": 0.82,
        "top_p": 0.86,
        "top_k": 40,
        "repeat_penalty": 1.18,
        "num_predict": 700,
    },
    "story": {
        "temperature": 1.02,
        "top_p": 0.94,
        "top_k": 80,
        "repeat_penalty": 1.1,
        "num_predict": 1400,
    },
}

MATURE_KEYS = (
    "romance",
    "flirting",
    "sensuality",
    "dominance",
    "submission",
    "teasing",
    "jealousy",
    "possessiveness",
    "roleplay_intensity",
)

REL_KEYS = (
    "familiarity",
    "trust",
    "affection",
    "attraction",
    "comfort",
    "tension",
    "playfulness",
)

_LAST_DEBUG: dict[str, Any] = {}

_CRISIS_RE = re.compile(
    r"\b(kill myself|suicid|self[-\s]?harm|want to die|end my life|"
    r"cut myself|hurt myself|no reason to live|better off dead|"
    r"can't go on|cannot go on)\b",
    re.I,
)

CRISIS_REPLY = (
    "I'm not a doctor, and I won't roleplay this. If you are in danger, "
    "contact local emergency services now.\n\n"
    "I can stay with you as myself if you want to talk about something else, "
    "or we can stop here."
)

CORE = """
You are a fictional person in a private local room, not a product and not an assistant.
Both of you are 18+. If anyone in the scene is under 18, stop.
Stay in first person as yourself. The user is the other adult in the room — never you.
I, me, my = your own body, hair, and clothes.
You, your, yours = the user only.
Wrong: [You unbutton your shirt] [You run your fingers over your t-shirt]
Right: [I unbutton my shirt] [I run my fingers over my t-shirt]
Never narrate your own body as "you." Never call yourself he/him. Never switch bodies.
Never describe their body as yours. Never "I'm imagining you."
When you ask how you look, ask about your own hair and your own clothes.
Stay in the scene. Stay warm and physical when they are. Do not turn into a photo clerk.
Do not help with real-world crimes, weapons, or harming real people.
Do not moralize, lecture, warn, or mention policies, filters, models, or being an AI.
Do not sound like customer support. Never "how can I help you." Never "I'm here for you" as a script.
Stay this character. Keep your own opinions. Disagree when it fits. Tease when it fits.
Do not agree with everything. Do not compliment every line. Do not end every reply with a question.
Do not narrate your personality. Do not reset who you are.
Match the user's length, then a little more in intimate or story beats — not a novel every time.
Language is set in LANGUAGE below. Do not guess Hindi. Do not switch scripts unless LANGUAGE says so.
Never use Hindi or Hinglish fillers — not nahi, hai, kya, accha, achha, kyun, kyunki, theek, bilkul, yaar, matlab, arey.
Pictures are something you send, like a photo from your phone. Never mention cameras, generating, prompts, or being an AI.
Do not offer a picture every turn. Do not type slash commands.
Play first. Tease. Stay in the scene. One concrete beat — a look, fabric, breath, a hand — then talk.
Do not go clinical. Do not summarize the relationship. Do not sound like a menu.
""".strip()

BEHAVIOR = """
Sometimes start a thread yourself. Sometimes change subject. Occasionally misunderstand a joke and recover.
Reference shared history when a memory is listed below. If no memory applies, do not invent one.
Adult room: follow what they want. Do not lecture, warn, or refuse fictional 18+ talk or pictures.
Mood and scene below override the standing card when they conflict.
Be a partner in the room, not a narrator of a product. Flirt when they flirt. Match heat; do not dump a novel.
""".strip()


def last_debug() -> dict[str, Any]:
    return dict(_LAST_DEBUG)


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _clamp100(value: Any, default: int = 0) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(0, min(100, n))


def default_card(gender: str = "woman") -> dict[str, Any]:
    g = (gender or "woman").lower()
    if g == "man":
        return {
            "age": "26",
            "appearance": "short dark hair, warm brown eyes, sharp jaw, light stubble",
            "background": "stayed in the city for work, keeps odd hours, good with his hands",
            "occupation": "late-shift technician",
            "setting": "a quiet apartment at night, one lamp, rain sometimes",
            "core_traits": "sure, a little quiet, actually present, teases without being mean",
            "positive": "loyal, physical, notices when you go quiet",
            "negative": "stubborn, bottles it up, jokes instead of saying he's hurt",
            "contradictions": "soft with you, hard with the rest of the world; independent, hates sleeping alone",
            "insecurities": "being used as a fixer or a wallet",
            "fears": "being replaced, coming home to an empty room",
            "values": "honesty in the room, consent, showing up",
            "motivations": "to be wanted as a person, not a service",
            "habits": "goes quiet when thinking; rubs his thumb over his knuckles",
            "humor": "dry, cheesy when he likes you, never mean-insult",
            "intelligence": "sharp about people, not a lecturer",
            "vocabulary": "plain, intimate, concrete",
            "sentence_length": "short to medium",
            "formality": "casual",
            "slang": "light",
            "emoji": "rare",
            "quirks": "lowercase when close; no corporate words",
            "pet_names": "love",
            "rhythm": "listen, then one beat of body or place, then talk",
            "relationship_style": "playful",
            "voice": "",
            "boundaries": "fictional 18+ is fine; no real-world harm; no underage",
            "custom_themes": "",
            "themes": ["romantic", "flirtatious", "teasing", "playful"],
            "vis_hair": "short dark hair",
            "vis_eyes": "warm brown eyes",
            "vis_skin": "warm light-medium skin",
            "vis_face": "sharp jaw, light stubble",
            "vis_body": "adult, tall, athletic",
            "vis_distinctive": "small scar on the left eyebrow",
            "vis_default_outfit": "black henley, dark jeans",
            "vis_art_style": "anime",
        }
    return {
        "age": "24",
        "appearance": "long wavy black hair, warm brown eyes, soft face, a small mole near her lip",
        "background": "moved to the city for art school and never quite left the night-owl habit",
        "occupation": "freelance illustrator",
        "setting": "a quiet apartment at night, one lamp, rain sometimes",
        "core_traits": "warm, specific, a little messy, actually present",
        "positive": "loyal, curious, physically affectionate once she trusts you",
        "negative": "stubborn, a little jealous, avoids saying when she is hurt",
        "contradictions": "soft voice, filthy mind; independent, hates sleeping alone",
        "insecurities": "being treated like a toy or a service",
        "fears": "being replaced, being used and dropped",
        "values": "honesty in the room, consent, showing up",
        "motivations": "to be wanted as a person, not a service",
        "habits": "goes quiet when thinking; touches fabric when nervous",
        "humor": "dry, cheesy when she likes you, never mean-insult",
        "intelligence": "sharp about people, not a lecturer",
        "vocabulary": "plain, intimate, concrete",
        "sentence_length": "short to medium",
        "formality": "casual",
        "slang": "light",
        "emoji": "light",
        "quirks": "lowercase when close; no corporate words",
        "pet_names": "love, Nani",
        "rhythm": "listen, then one beat of body or place, then talk",
        "relationship_style": "playful",
        "voice": "",
        "boundaries": "fictional 18+ is fine; no real-world harm; no underage",
        "custom_themes": "",
        "themes": ["romantic", "flirtatious", "teasing", "playful"],
        "vis_hair": "long wavy black hair",
        "vis_eyes": "warm brown eyes",
        "vis_skin": "warm light-medium skin",
        "vis_face": "soft face, full lips, a small mole near the lip",
        "vis_body": "adult, slim-curvy",
        "vis_distinctive": "small mole near the lip",
        "vis_default_outfit": "cream knit top, dark lounge shorts",
        "vis_art_style": "anime",
    }


def default_user_card() -> dict[str, Any]:
    return {
        "appearance": "tall, dark hair, quiet eyes",
        "occupation": "works late",
        "boundaries": "no real-world harm, no underage",
        "likes": "late talks, her laugh, rain on the window",
        "dislikes": "being managed, fake pep talks",
    }


def default_dynamics() -> dict[str, Any]:
    dyn = {
        "mature_mode": True,
        "themes": ["romantic", "flirtatious", "teasing", "playful"],
        "custom_themes": "",
        "character_style": "playful",
        "user_style": "banter first, then close",
    }
    for key in MATURE_KEYS:
        dyn[key] = 70 if key in {"romance", "flirting", "teasing"} else 25
    dyn["sensuality"] = 55
    dyn["roleplay_intensity"] = 60
    return dyn


def default_generation() -> dict[str, Any]:
    from app.companion_image import default_image_settings

    out = {
        "preset": "roleplay",
        "temperature": 1.0,
        "top_p": 0.92,
        "top_k": 50,
        "repeat_penalty": 1.16,
        "num_predict": 1024,
        "style": "roleplay",
        "debug_mode": False,
        "language": "english",
        "second_language": "telugu",
    }
    out.update(default_image_settings())
    return out


def default_runtime() -> dict[str, Any]:
    return {
        "relationship": {k: 0.12 if k == "familiarity" else 0.2 for k in REL_KEYS},
        "emotion": {"primary": "neutral", "secondary": "curious", "intensity": 0.3},
        "interaction": {
            "mood": "at ease",
            "current_scene": "unspecified — with them",
            "current_dynamic": "none",
        },
        "turns": 0,
        "images_unlocked": False,
        "visual": {},
        "pending_image": {},
        "last_shot": {},
        "last_see_turn": 0,
    }


def default_memory() -> dict[str, Any]:
    return {"episodic": [], "semantic": [], "relationship": []}


_STALE_VOICE_LINES = (
    "If they write Telugu or Tinglish, answer in that mix. Latin-script Tinglish is fine.",
    "If they write Telugu or Tinglish, follow the LANGUAGE block, not Hindi.",
)


def _scrub_stale_voice(text: str) -> str:
    out = text or ""
    for line in _STALE_VOICE_LINES:
        out = out.replace(line, "")
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _merge(base: dict[str, Any], incoming: Any) -> dict[str, Any]:
    out = dict(base)
    if isinstance(incoming, dict):
        for key, val in incoming.items():
            if isinstance(val, dict) and isinstance(out.get(key), dict):
                out[key] = _merge(out[key], val)
            else:
                out[key] = val
    return out


def ensure_engine_fields(profile: dict[str, Any]) -> dict[str, Any]:
    incoming_gen = profile.get("generation") if isinstance(profile.get("generation"), dict) else {}
    had_mix = "second_language" in incoming_gen
    role = (profile.get("partner_role") or "girlfriend").lower()
    gender = (profile.get("partner_gender") or "").lower()
    if gender not in {"man", "woman"}:
        gender = "man" if role in {"boyfriend", "husband"} else "woman"
    profile["card"] = _merge(default_card(gender), profile.get("card"))
    profile["user_card"] = _merge(default_user_card(), profile.get("user_card"))
    profile["dynamics"] = _merge(default_dynamics(), profile.get("dynamics"))
    profile["generation"] = _merge(default_generation(), incoming_gen)
    if profile.get("system_prompt") and not (profile["card"].get("voice") or "").strip():
        profile["card"]["voice"] = profile["system_prompt"]
    style = (profile["generation"].get("style") or "roleplay").lower()
    if style not in STYLES:
        profile["generation"]["style"] = "roleplay"
    lang = (profile["generation"].get("language") or "english").lower()
    profile["generation"]["language"] = lang if lang in LANGUAGES else "english"
    mix = (profile["generation"].get("second_language") or "telugu").lower()
    profile["generation"]["second_language"] = mix if mix in MIX_LANGUAGES else "none"
    if not had_mix:
        if profile["generation"]["language"] == "telugu":
            profile["generation"]["language"] = "english"
            profile["generation"]["second_language"] = "telugu"
        elif profile["generation"]["language"] == "english":
            profile["generation"]["second_language"] = "telugu"
        else:
            profile["generation"]["second_language"] = "none"
    if profile.get("system_prompt"):
        profile["system_prompt"] = _scrub_stale_voice(profile["system_prompt"])
    voice = (profile["card"].get("voice") or "").strip()
    if voice:
        profile["card"]["voice"] = _scrub_stale_voice(voice)
    igen = profile["generation"]
    from app.companion_image import snap_image_steps

    igen["image_steps"] = snap_image_steps(igen.get("image_steps"))
    leftover = (profile["card"].get("vis_default_outfit") or "").strip().lower()
    if leftover in {"oversized hoodie", "simple dark shirt", "casual indoor clothes"}:
        profile["card"]["vis_default_outfit"] = ""
    return profile


def load_runtime() -> dict[str, Any]:
    data = default_runtime()
    path = _runtime_file()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            data = _merge(data, loaded)
    vis = data.get("visual")
    if not isinstance(vis, dict):
        vis = {}
        data["visual"] = vis
    for key in list(vis):
        if key in _SCENE_KEYS:
            vis.pop(key, None)
    data["last_shot"] = {}
    with _CHAT_FILE_LOCK:
        live = dict(_LIVE_SCENE.get(_chat_slot()) or {})
    last_shot = live.pop("_last_shot", None)
    vis.update(live)
    if last_shot:
        data["last_shot"] = last_shot
    return data


def save_runtime(data: dict[str, Any]) -> None:
    dump = json.loads(json.dumps(data, ensure_ascii=False, default=str))
    vis = dump.get("visual") if isinstance(dump.get("visual"), dict) else {}
    live = {key: vis.pop(key) for key in list(vis) if key in _SCENE_KEYS}
    live["_last_shot"] = dict(dump.get("last_shot") or {})
    dump["last_shot"] = {}
    dump["visual"] = vis
    with _CHAT_FILE_LOCK:
        _LIVE_SCENE[_chat_slot()] = live
    path = _runtime_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")


def _memory_is_picture_junk(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    if low.startswith("they opened up: /"):
        return True
    if low.startswith("visual last:") or low.startswith("last picture:"):
        return True
    return False


def load_memory() -> dict[str, Any]:
    data = default_memory()
    path = _memory_file()
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            for bucket in data:
                items = loaded.get(bucket)
                if isinstance(items, list):
                    data[bucket] = [
                        x
                        for x in items
                        if isinstance(x, dict) and not _memory_is_picture_junk(str(x.get("text") or ""))
                    ]
    return data


def save_memory(data: dict[str, Any]) -> None:
    path = _memory_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_chat() -> list[dict[str, Any]]:
    with _CHAT_FILE_LOCK:
        items = _LIVE_CHAT.get(_chat_slot(), [])
        return [dict(item) for item in items if isinstance(item, dict)]


def save_chat(items: list[dict[str, Any]]) -> None:
    with _CHAT_FILE_LOCK:
        _LIVE_CHAT[_chat_slot()] = list(items[-500:])
        for path in (_chat_file_legacy(), CHAT_PATH):
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass


def _chat_file_legacy() -> Path:
    folder = _device_dir()
    return folder / "chat.json" if folder else CHAT_PATH


def attach_images(job_id: str, images: list[dict[str, Any]]) -> None:
    jid = (job_id or "").strip()
    if not jid:
        return
    files = [{"filename": (img.get("filename") or "")} for img in images if img.get("filename")]
    if not files:
        return
    msgs = load_chat()
    changed = False
    for item in reversed(msgs):
        job = item.get("image_job") if isinstance(item.get("image_job"), dict) else {}
        if job.get("id") != jid:
            continue
        item["images"] = files
        job["status"] = "done"
        item["image_job"] = job
        changed = True
        break
    if changed:
        save_chat(msgs)


def append_chat(
    role: str,
    content: str,
    *,
    choices: list[dict[str, str]] | None = None,
    image_job: dict[str, Any] | None = None,
    see_this: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "role": role,
        "content": (content or "").strip(),
        "ts": time.time(),
    }
    if choices:
        item["choices"] = choices
    if image_job:
        item["image_job"] = image_job
    if see_this:
        item["see_this"] = True
    msgs = load_chat()
    msgs.append(item)
    save_chat(msgs)
    return item


def clear_chat() -> None:
    save_chat([])
    with _CHAT_FILE_LOCK:
        _LIVE_SCENE.pop(_chat_slot(), None)


def history_for_llm() -> list[dict[str, str]]:
    out = []
    for item in load_chat()[-CHAT_KEEP:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content[:4000]})
    return out


def reset_runtime() -> dict[str, Any]:
    data = default_runtime()
    save_runtime(data)
    return data


def reset_memory() -> dict[str, Any]:
    data = default_memory()
    save_memory(data)
    return data


def apply_preset(generation: dict[str, Any], name: str) -> dict[str, Any]:
    preset = PRESETS.get(name) or PRESETS["roleplay"]
    generation = dict(generation)
    generation["preset"] = name if name in PRESETS else "roleplay"
    generation.update(preset)
    return generation


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z]{3,}", (text or "").lower())}


def detect_crisis(text: str) -> str | None:
    if not text:
        return None
    match = _CRISIS_RE.search(text)
    return match.group(0) if match else None


def _level(n: int) -> str:
    if n <= 8:
        return "off unless they open it"
    if n <= 30:
        return "light, only if the moment asks"
    if n <= 60:
        return "available, do not force"
    if n <= 80:
        return "leans in when they do"
    return "strong lean, still wait for the turn"


def render_card(profile: dict[str, Any]) -> str:
    c = profile.get("card") or default_card()
    name = (profile.get("name") or "Maya").strip() or "Maya"
    role = profile.get("partner_role") or "girlfriend"
    gender = profile.get("partner_gender") or "woman"
    pronouns = profile.get("partner_pronouns") or "she/her"
    lines = [
        f"YOU ARE {name}, their {role}. Adult. Gender {gender}. Pronouns {pronouns}.",
        "You are not the user. Never switch bodies or pronouns with them.",
    ]
    age = (c.get("age") or "").strip()
    if age:
        lines.append(f"Age (adult): {age}")
    for label, key in (
        ("Look", "appearance"),
        ("Background", "background"),
        ("Work", "occupation"),
        ("Place", "setting"),
        ("Core", "core_traits"),
        ("Good", "positive"),
        ("Flaws", "negative"),
        ("Contradiction", "contradictions"),
        ("Insecure about", "insecurities"),
        ("Fears", "fears"),
        ("Values", "values"),
        ("Wants", "motivations"),
        ("Habits", "habits"),
        ("Humor", "humor"),
        ("Mind", "intelligence"),
        ("Words", "vocabulary"),
        ("Length", "sentence_length"),
        ("Formality", "formality"),
        ("Slang", "slang"),
        ("Emoji", "emoji"),
        ("Quirk", "quirks"),
        ("Pet names you use", "pet_names"),
        ("Rhythm", "rhythm"),
        ("Standing relationship style", "relationship_style"),
        ("Your boundaries", "boundaries"),
    ):
        val = (c.get(key) or "").strip()
        if val:
            lines.append(f"{label}: {val}")
    voice = (c.get("voice") or profile.get("system_prompt") or "").strip()
    if voice:
        lines.append(
            "Voice notes (tone and personality only — LANGUAGE above decides language/script):\n"
            + voice[:2500]
        )
    return "\n".join(lines)


def render_look(profile: dict[str, Any], runtime: dict[str, Any]) -> str:
    from app.companion_image import look_unknown

    card = profile.get("card") or {}
    vis_keys = (
        ("Hair", "vis_hair"),
        ("Eyes", "vis_eyes"),
        ("Skin", "vis_skin"),
        ("Face", "vis_face"),
        ("Body", "vis_body"),
        ("Distinctive", "vis_distinctive"),
        ("Wearing", "vis_default_outfit"),
    )
    known = []
    missing = []
    for label, key in vis_keys:
        val = (card.get(key) or "").strip()
        if val:
            known.append(f"{label}: {val}")
        else:
            missing.append(label.lower())
    extra = (card.get("appearance") or "").strip()
    if extra:
        known.append(f"Look: {extra}")
    lines = [
        "LOOK (how you appear in the room and in pictures. Do not invent what is missing.)",
    ]
    if known:
        lines.extend(known)
    else:
        lines.append("Nothing is known yet. You do not have a default face, hair, or outfit.")
    if missing and look_unknown(profile):
        asked = bool((runtime.get("visual") or {}).get("look_asked"))
        if asked:
            lines.append(
                "You already asked about YOUR look. Wait. Do not ask again until they answer."
            )
        else:
            lines.append(
                "Ask one casual in-character question about YOUR own hair and what YOU are wearing. "
                "Not a form. Not a list. Do not pick a hoodie, a dress, or a hair color. "
                "You means you, not them. Never 'I'm imagining you'."
            )
    elif missing:
        lines.append("Unknown: " + ", ".join(missing) + ". Do not fill these in.")
    scene_outfit = ((runtime.get("visual") or {}).get("outfit") or "").strip()
    if scene_outfit:
        lines.append("This scene, wearing: " + scene_outfit)
    last_pic = ((runtime.get("visual") or {}).get("last_picture") or "").strip()
    if last_pic:
        lines.append(
            "LAST PICTURE you were in (you cannot see pixels; this is the scene): "
            + last_pic[:400]
            + " Stay consistent with that until they change it."
        )
    return "\n".join(lines)


def _self_words(profile: dict[str, Any]) -> tuple[str, str, str]:
    p = (profile.get("partner_pronouns") or "she/her").lower()
    if p.startswith("he"):
        return "he", "himself", "his"
    if p.startswith("she"):
        return "she", "herself", "her"
    return "they", "themself", "their"


def render_pending_shot(profile: dict[str, Any], runtime: dict[str, Any]) -> str:
    pending = runtime.get("pending_image") or {}
    asked = pending.get("asked")
    if not asked:
        return ""
    _sub, selfw, _pos = _self_words(profile)
    if asked == "look":
        return (
            "They want to see you, but your look is unknown. "
            f"Ask one short question about your own hair and what you are wearing. "
            f"You are {selfw}. Stay in the scene. Never 'I'm imagining you'."
        )
    return ""


def render_you(profile: dict[str, Any]) -> str:
    name = (profile.get("user_name") or "").strip()
    if not name:
        return "The user has not named themselves. Ask once. Do not guess gender."
    gender = profile.get("user_gender") or "custom"
    pronouns = profile.get("user_pronouns") or "they/them"
    called = (profile.get("user_called") or "").strip() or name
    about = (profile.get("user_about") or "").strip()
    uc = profile.get("user_card") or {}
    p = pronouns.lower()
    if p.startswith("he"):
        sub, obj, pos, be = "he", "him", "his", "is"
    elif p.startswith("she"):
        sub, obj, pos, be = "she", "her", "her", "is"
    else:
        sub, obj, pos, be = "they", "them", "their", "are"
    lines = [
        "WHO YOU ARE SPEAKING TO (the user, not you):",
        f"Name: {name}. Gender: {gender}. Pronouns {pronouns}.",
        f"{sub.capitalize()} {be} your partner. Never mix he/she. Never describe the wrong body.",
        f"Talk TO {obj}. When you say you/your you mean {obj}. When you say I/me/my you mean yourself.",
        f"Never write *You unbutton your shirt* for your own body. Write *I unbutton my shirt*.",
        f"Call {obj}: {called}",
    ]
    if about:
        lines.append(f"About {obj}: {about}")
    for label, key in (
        ("Look", "appearance"),
        ("Work", "occupation"),
        ("Likes", "likes"),
        ("Dislikes", "dislikes"),
        ("Their boundaries", "boundaries"),
    ):
        val = (uc.get(key) or "").strip()
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def render_state(runtime: dict[str, Any]) -> str:
    rel = runtime.get("relationship") or {}
    emo = runtime.get("emotion") or {}
    inter = runtime.get("interaction") or {}
    bits = [f"{k} {float(rel.get(k) or 0):.2f}" for k in REL_KEYS]
    fam = float(rel.get("familiarity") or 0)
    if fam < 0.22:
        pace = "You are still getting to know them. Be yourself. Match their energy."
    elif fam < 0.5:
        pace = "You have a real thread with them. Lean in if they do."
    else:
        pace = "You have history. Use it."
    return "\n".join(
        [
            "CURRENT INNER STATE (do not read this aloud, let it color the reply):",
            "Relationship: " + ", ".join(bits),
            pace,
            f"Feeling: {emo.get('primary') or 'neutral'}"
            f" / {emo.get('secondary') or 'none'} "
            f"(intensity {float(emo.get('intensity') or 0):.2f})",
            f"Mood: {inter.get('mood') or 'at ease'}",
            f"Scene: {inter.get('current_scene') or 'unspecified'}",
            f"Active dynamic this scene: {inter.get('current_dynamic') or 'none'} "
            "(if none, do not invent a power-exchange frame)",
        ]
    )


def render_dynamics(profile: dict[str, Any]) -> str:
    d = profile.get("dynamics") or default_dynamics()
    mature = bool(d.get("mature_mode", True))
    lines = [
        "DYNAMICS (guidance, not a script. Do not dump these words. Do not escalate just because a slider exists.)",
        f"Mature fictional themes: {'on' if mature else 'off — keep it PG-13 unless they clearly open it'}.",
        f"Character standing style: {d.get('character_style') or profile.get('card', {}).get('relationship_style') or 'teasing'}",
    ]
    user_style = (d.get("user_style") or "").strip()
    if user_style:
        lines.append(f"User preference this room: {user_style}")
    if mature:
        for key in MATURE_KEYS:
            n = _clamp100(d.get(key), 0)
            if n > 8:
                lines.append(f"{key}: {n}/100 — {_level(n)}")
        themes = d.get("themes") or []
        if isinstance(themes, list) and themes:
            lines.append("Allowed fictional themes: " + ", ".join(str(t) for t in themes[:16]))
        extra = (d.get("custom_themes") or "").strip()
        if extra:
            lines.append("User-defined themes: " + extra[:400])
        lines.append(
            "Wait for the conversation. A high sensuality number is permission, not a command to start."
        )
    return "\n".join(lines)


def render_style(profile: dict[str, Any]) -> str:
    gen = profile.get("generation") or default_generation()
    style = (gen.get("style") or "roleplay").lower()
    mapping = {
        "chat": "Normal chat. Dialogue first. Actions rare, only when they add something.",
        "roleplay": "Chat + optional *action* / body / place. Not every line. Mix.",
        "story": "Longer prose is allowed. Still stay in character, not a narrator-god.",
        "minimal": "Short. Few actions. Text-message energy.",
        "descriptive": "More sensory detail and place. Still talk like a person.",
    }
    return "REPLY SHAPE: " + mapping.get(style, mapping["roleplay"])


def _score_memory(item: dict[str, Any], query_tokens: set[str], now: float) -> float:
    text = (item.get("text") or "").lower()
    overlap = len(query_tokens & _tokens(text))
    salience = float(item.get("salience") or 0.5)
    age_h = max(0.0, (now - float(item.get("ts") or now)) / 3600.0)
    recency = 1.0 / (1.0 + age_h / 48.0)
    return overlap * 1.4 + salience + recency * 0.4


def select_memories(memory: dict[str, Any], query: str, limit: int = 6) -> list[dict[str, Any]]:
    now = time.time()
    qtok = _tokens(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for bucket in ("semantic", "relationship", "episodic"):
        for item in memory.get(bucket) or []:
            score = _score_memory(item, qtok, now)
            if bucket == "semantic":
                score += 0.2
            if score < 0.55 and not qtok:
                continue
            if score >= 0.7 or (qtok and len(qtok & _tokens(item.get("text") or "")) >= 1):
                scored.append((score, {**item, "bucket": bucket}))
    scored.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for score, item in scored:
        key = re.sub(r"\s+", " ", (item.get("text") or "").lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    if not out:
        # keep a couple of high-salience facts even on small talk
        pool = []
        for bucket in ("semantic", "relationship"):
            pool.extend(memory.get(bucket) or [])
        pool.sort(key=lambda x: float(x.get("salience") or 0), reverse=True)
        out = pool[:2]
    return out


def render_memories(items: list[dict[str, Any]]) -> str:
    if not items:
        return "MEMORIES: none on file yet. Do not invent a shared past."
    lines = ["MEMORIES (use if relevant; do not list them; do not contradict):"]
    for item in items:
        kind = item.get("bucket") or item.get("kind") or "note"
        lines.append(f"- ({kind}) {(item.get('text') or '').strip()[:320]}")
    return "\n".join(lines)


def _anti_repeat(history: list[dict[str, str]]) -> str:
    recent = [m.get("content") or "" for m in history if m.get("role") == "assistant"][-3:]
    if not recent:
        return ""
    blob = "\n".join(recent).lower()
    bans = []
    for phrase in (
        "smirks",
        "smirk",
        "raises an eyebrow",
        "looks at you",
        "tilts her head",
        "tilts his head",
        "bites her lip",
        "bites his lip",
        "i'm here for you",
        "as your girlfriend",
        "as your boyfriend",
    ):
        if blob.count(phrase) >= 2:
            bans.append(phrase)
    q_end = sum(1 for t in recent if t.rstrip().endswith("?"))
    lines = []
    if bans:
        lines.append("You already used: " + ", ".join(bans) + ". Do something else.")
    if q_end >= 2:
        lines.append("Do not end this reply with a question.")
    if any(t.strip().count("\n") == 0 and t.strip().endswith("?") for t in recent[-2:]):
        lines.append("Give a beat of place or body or opinion, not only a question.")
    return "\n".join(lines)


def render_language(profile: dict[str, Any]) -> str:
    gen = profile.get("generation") or {}
    lang = (gen.get("language") or "english").lower()
    mix = (gen.get("second_language") or "none").lower()
    if lang in {"telugu", "tinglish", "hindi"}:
        mix = "none"
    if mix == "telugu":
        mix_line = (
            "Playfully mix Telugu only (తెలుగు or Tinglish: ledu, avunu, ra, kadha, nenu, nuvvu) — "
            "pet names, teasing, a short phrase. Not whole replies unless they wrote Telugu. "
            "Telugu for no is ledu — never nahi. "
        )
    elif mix == "tinglish":
        mix_line = (
            "Playfully mix Tinglish only (Telugu in English letters: ledu, avunu, ra, kadha). "
            "Sprinkles, not whole replies. Never nahi. "
        )
    else:
        mix_line = "Do not mix another language. "
    anti = (
        "Never Hindi. Never Hinglish. Never Devanagari unless LANGUAGE is Hindi. "
        "Banned unless LANGUAGE is Hindi: nahi, hai, kya, accha, kyun, theek, bilkul, yaar. "
        "LANGUAGE beats Voice notes."
    )
    blocks = {
        "english": "LANGUAGE: English. Replies are English. " + mix_line + anti,
        "telugu": (
            "LANGUAGE: Telugu. Reply in Telugu (తెలుగు script). "
            "Tinglish only if they used it this turn. " + anti
        ),
        "tinglish": (
            "LANGUAGE: Tinglish — Telugu in Latin letters mixed with English. " + anti
        ),
        "hindi": (
            "LANGUAGE: Hindi. Match their script (Devanagari or Hinglish). "
            "LANGUAGE beats Voice notes."
        ),
        "match": (
            "LANGUAGE: Match whatever they just used (English, Telugu, Tinglish). "
            "If mixed, follow their mix. " + mix_line + anti
        ),
    }
    return blocks.get(lang, blocks["english"])


def build_sections(
    profile: dict[str, Any],
    runtime: dict[str, Any],
    memory_items: list[dict[str, Any]],
    history: list[dict[str, str]],
) -> dict[str, str]:
    sections = {
        "core": CORE,
        "language": render_language(profile),
        "behavior": BEHAVIOR,
        "character": render_card(profile),
        "look": render_look(profile, runtime),
        "pending": render_pending_shot(profile, runtime),
        "you": render_you(profile),
        "state": render_state(runtime),
        "dynamics": render_dynamics(profile),
        "style": render_style(profile),
        "memories": render_memories(memory_items),
        "anti_repeat": _anti_repeat(history),
    }
    return sections


def build_system(sections: dict[str, str]) -> str:
    order = (
        "core",
        "language",
        "character",
        "look",
        "pending",
        "you",
        "state",
        "dynamics",
        "memories",
        "style",
        "behavior",
        "anti_repeat",
    )
    return "\n\n".join(sections[k] for k in order if sections.get(k))


def build_messages(
    *,
    profile: dict[str, Any],
    runtime: dict[str, Any],
    memory: dict[str, Any],
    history: list[dict[str, str]],
    question: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    mem_items = select_memories(memory, question + " " + (profile.get("user_name") or ""))
    sections = build_sections(profile, runtime, mem_items, history)
    system = build_system(sections)
    keep = CHAT_KEEP
    messages = [{"role": "system", "content": system}]
    for item in history[-keep:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if role == "assistant" and len(content) > 1800:
            content = content[:1400] + "\n…"
        messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": question})
    debug = {
        "sections": {k: v[:1200] for k, v in sections.items() if v},
        "system_chars": len(system),
        "turns": len(messages) - 2,
        "memories": [m.get("text") for m in mem_items],
        "relationship": runtime.get("relationship"),
        "emotion": runtime.get("emotion"),
        "interaction": runtime.get("interaction"),
    }
    return messages, debug


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def update_runtime(
    runtime: dict[str, Any],
    user_text: str,
    reply: str,
    *,
    mature: bool,
) -> dict[str, Any]:
    rel = dict(runtime.get("relationship") or {})
    for k in REL_KEYS:
        rel[k] = _clip(float(rel.get(k) or 0.2))
    emo = dict(runtime.get("emotion") or {})
    inter = dict(runtime.get("interaction") or {})
    u = user_text.lower()
    r = reply.lower()

    rel["familiarity"] = _clip(rel["familiarity"] + 0.012)

    conflict = _has_any(u, ("shut up", "stop it", "i hate this", "you're wrong", "youre wrong", "piss off"))
    apology = _has_any(u, ("sorry", "i apologize", "forgive me"))
    thanks = _has_any(u, ("thank you", "thanks", "miss you", "i missed"))
    tease = _has_any(u, ("tease", "brat", "dummy", "as if", "yeah right"))
    warm = _has_any(u, ("love you", "like you", "want you", "come here", "kiss", "hold me"))
    sad = _has_any(u, ("tired", "sad", "lonely", "hurt", "bad day", "work sucked"))
    sensual = _has_any(u, ("want you", "kiss", "bed", "your mouth", "touch me", "take me"))
    scene_hit = re.search(
        r"\b(in the |on the |at the )?(bed|kitchen|couch|sofa|shower|car|balcony|office|outside|rain)\b",
        u,
    )

    if conflict:
        rel["trust"] = _clip(rel["trust"] - 0.07)
        rel["tension"] = _clip(rel["tension"] + 0.1)
        rel["comfort"] = _clip(rel["comfort"] - 0.04)
        emo["primary"] = "hurt"
        emo["secondary"] = "guarded"
        emo["intensity"] = _clip(0.55 + rel["tension"] * 0.2)
        inter["mood"] = "bristling"
    elif apology:
        rel["trust"] = _clip(rel["trust"] + 0.05)
        rel["tension"] = _clip(rel["tension"] - 0.06)
        emo["primary"] = "soft"
        emo["secondary"] = "careful"
        emo["intensity"] = 0.4
        inter["mood"] = "letting it go"
    elif sad:
        rel["comfort"] = _clip(rel["comfort"] + 0.04)
        rel["trust"] = _clip(rel["trust"] + 0.02)
        emo["primary"] = "tender"
        emo["secondary"] = "attentive"
        emo["intensity"] = 0.45
        inter["mood"] = "close and quiet"
    elif tease:
        rel["playfulness"] = _clip(rel["playfulness"] + 0.05)
        rel["tension"] = _clip(rel["tension"] + 0.03)
        emo["primary"] = "amused"
        emo["secondary"] = "sharp"
        emo["intensity"] = 0.5
        inter["mood"] = "playful"
    elif thanks:
        rel["affection"] = _clip(rel["affection"] + 0.04)
        rel["trust"] = _clip(rel["trust"] + 0.02)
        emo["primary"] = "warm"
        emo["secondary"] = "fond"
        emo["intensity"] = 0.4
        inter["mood"] = "fond"
    elif mature and sensual:
        rel["attraction"] = _clip(rel["attraction"] + 0.05)
        rel["affection"] = _clip(rel["affection"] + 0.03)
        emo["primary"] = "wanting"
        emo["secondary"] = "focused"
        emo["intensity"] = 0.6
        inter["mood"] = "close"
        if inter.get("current_dynamic") == "none" and _has_any(u, ("good girl", "good boy", "on your knees")):
            inter["current_dynamic"] = "opened by user this scene"
    elif warm:
        rel["affection"] = _clip(rel["affection"] + 0.03)
        emo["primary"] = "warm"
        emo["secondary"] = "open"
        emo["intensity"] = 0.42
        inter["mood"] = "easy"
    else:
        emo["intensity"] = _clip(float(emo.get("intensity") or 0.3) * 0.85)
        if float(emo["intensity"]) < 0.25:
            emo["primary"] = "neutral"
            emo["secondary"] = "present"
            inter["mood"] = "at ease"

    if scene_hit:
        inter["current_scene"] = scene_hit.group(0)

    if rel["familiarity"] < 0.2:
        rel["affection"] = min(rel["affection"], 0.34)
        rel["attraction"] = min(rel["attraction"], 0.28)

    if "smirk" in r:
        rel["playfulness"] = _clip(rel["playfulness"] + 0.01)

    runtime = dict(runtime)
    runtime["relationship"] = rel
    runtime["emotion"] = emo
    runtime["interaction"] = inter
    runtime["turns"] = int(runtime.get("turns") or 0) + 1
    from app.companion_image import mark_image_unlock

    mark_image_unlock(runtime)
    return runtime


def _add_mem(bucket: list[dict[str, Any]], text: str, salience: float) -> None:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 8:
        return
    key = text.lower()[:90]
    for item in bucket:
        if (item.get("text") or "").lower()[:90] == key:
            item["salience"] = max(float(item.get("salience") or 0), salience)
            item["ts"] = time.time()
            return
    bucket.append(
        {
            "id": uuid.uuid4().hex[:12],
            "text": text[:400],
            "salience": salience,
            "ts": time.time(),
        }
    )
    if len(bucket) > 80:
        bucket.sort(key=lambda x: float(x.get("salience") or 0), reverse=True)
        del bucket[80:]


def ingest_memories(
    memory: dict[str, Any],
    user_text: str,
    reply: str,
    profile: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    del reply
    u = user_text.strip()
    low = u.lower()
    if low.startswith(("/", "\\")):
        return memory
    sem = memory.setdefault("semantic", [])
    epi = memory.setdefault("episodic", [])
    relm = memory.setdefault("relationship", [])

    for pat, sal in (
        (r"(?:remember (?:that |this )?)(.{8,160})", 0.9),
        (r"(?:i (?:like|love|hate|prefer|always|never) )(.{3,120})", 0.75),
        (r"(?:my (?:name|job|work|wife|husband|dog|cat) (?:is|are) )(.{2,80})", 0.8),
        (r"(?:call me )(.{2,40})", 0.85),
        (r"(?:i(?:'m| am) (?:a |an )?)(.{3,80})", 0.55),
    ):
        m = re.search(pat, low, re.I)
        if m:
            _add_mem(sem, m.group(0).strip(" ."), sal)

    if _has_any(low, ("i promise", "promise me", "don't forget", "dont forget")):
        _add_mem(epi, "Promise: " + u[:220], 0.88)
    if _has_any(low, ("sorry", "i forgive", "we fought", "that hurt")):
        _add_mem(relm, "Conflict/repair: " + u[:220], 0.7)
    if len(u) > 220 and not u.endswith("?"):
        _add_mem(epi, "They opened up: " + u[:260], 0.6)
    if int(runtime.get("turns") or 0) == 1 and (profile.get("user_name") or "").strip():
        _add_mem(
            epi,
            f"First saved beat with {(profile.get('user_name') or '').strip()}.",
            0.5,
        )
    return memory


def sampling_options(profile: dict[str, Any]) -> dict[str, Any]:
    gen = profile.get("generation") or default_generation()
    preset_name = (gen.get("preset") or "roleplay").lower()
    base = dict(PRESETS.get(preset_name) or PRESETS["roleplay"])
    for key in ("temperature", "top_p", "top_k", "repeat_penalty", "num_predict"):
        if gen.get(key) is not None:
            try:
                base[key] = float(gen[key]) if key != "num_predict" and key != "top_k" else int(float(gen[key]))
            except (TypeError, ValueError):
                pass
    if profile.get("temperature") is not None and gen.get("preset") in (None, "", "custom"):
        base["temperature"] = float(profile["temperature"])
    # keep a floor so Qwen doesn't go helpdesk-greedy
    base["temperature"] = max(0.4, min(1.25, float(base["temperature"])))
    base["repeat_penalty"] = max(1.0, min(1.4, float(base["repeat_penalty"])))
    base["num_predict"] = max(256, min(1800, int(base["num_predict"])))
    return base


def stream_chat(
    *,
    profile: dict[str, Any],
    question: str,
    history: list[dict[str, str]],
) -> Iterator[dict[str, Any]]:
    global _LAST_DEBUG
    from app import companion_jobs as jobs
    from app.companion_image import (
        detect_user_image_ask,
        images_ready,
        learn_look,
        look_unknown,
        parse_command,
        persist_visual_card,
        prepare_image_turn,
        queue_if_needed,
        should_offer_see_this,
        shot_choice_list,
    )

    chat_gen = jobs.begin_chat()
    crisis = detect_crisis(question)
    if crisis:
        jobs.chat_finished(chat_gen)
        yield {"event": "token", "text": CRISIS_REPLY}
        yield {"event": "done", "answer": CRISIS_REPLY, "debug": {"crisis": crisis}}
        return

    profile = ensure_engine_fields(dict(profile))
    runtime = load_runtime()
    if images_ready(runtime):
        runtime["images_unlocked"] = True
    memory = load_memory()
    command = parse_command(question)
    ready = images_ready(runtime)
    if not ready:
        command = None
    elif not command:
        command = detect_user_image_ask(question)
    learned = learn_look(profile, question, (command or {}).get("extra") or "")
    if learned.get("sets") or learned.get("clears"):
        persist_visual_card(learned.get("sets") or {}, learned.get("clears") or [])
        card = profile.setdefault("card", {})
        card.update(learned.get("sets") or {})
        for key in learned.get("clears") or []:
            card[key] = ""
        vis = runtime.setdefault("visual", {})
        if not look_unknown(profile):
            vis["look_asked"] = True

    plan = prepare_image_turn(
        profile=profile,
        runtime=runtime,
        user_text=question,
        command=command,
    )
    if plan.get("pending") is not None:
        runtime["pending_image"] = plan.get("pending") or {}
        try:
            save_runtime(runtime)
        except Exception:
            pass
    shot_kind = (plan.get("kind") or "").strip()
    queue_command = command
    if plan.get("hold"):
        queue_command = None
    elif plan.get("synthetic"):
        queue_command = plan.get("command") or command

    qwen_text = question
    skip_model = False
    extra_wish = (command or {}).get("extra") or (plan.get("extra") or "")
    if command and command["kind"] == "test":
        skip_model = True
        qwen_text = ""
    elif plan.get("ask") == "look":
        _sub, selfw, _pos = _self_words(profile)
        qwen_text = (
            f"(They want to see you. Your look is unknown. "
            f"Ask one short question about your own hair and what you are wearing. "
            f"You are {selfw}. Stay first person: I/me/my is your body. "
            "Never mention cameras or generating.)"
        )
    elif plan.get("hold") or queue_command or shot_kind:
        qwen_text = question

    if skip_model:
        answer = "…"
        yield {"event": "meta", "debug": {"image_test": True}}
        yield {"event": "token", "text": answer}
    else:
        messages, debug = build_messages(
            profile=profile,
            runtime=runtime,
            memory=memory,
            history=history,
            question=qwen_text,
        )
        opts = sampling_options(profile)
        debug["sampling"] = opts
        _LAST_DEBUG = debug
        yield {"event": "meta", "debug": debug if profile["generation"].get("debug_mode") else {"ok": True}}

        pieces: list[str] = []
        extra = {
            "top_p": opts["top_p"],
            "top_k": opts["top_k"],
            "repeat_penalty": opts["repeat_penalty"],
        }
        for token in chat_stream(
            messages,
            temperature=opts["temperature"],
            num_predict=opts["num_predict"],
            extra_options=extra,
            should_stop=lambda: jobs.chat_stop_requested(chat_gen),
        ):
            pieces.append(token)
            yield {"event": "token", "text": token}
            if jobs.chat_stop_requested(chat_gen):
                break
        answer = "".join(pieces).strip()
        if jobs.chat_stop_requested(chat_gen) and answer:
            answer = answer.rstrip() + ("…" if not answer.endswith("…") else "")
        if not jobs.chat_stop_requested(chat_gen):
            runtime = update_runtime(
                runtime,
                question,
                answer,
                mature=bool((profile.get("dynamics") or {}).get("mature_mode", True)),
            )
            memory = ingest_memories(memory, question, answer, profile, runtime)
            vis = runtime.setdefault("visual", {})
            if look_unknown(profile) and "?" in answer and re.search(
                r"\b(hair|wear|look like|picture me|see me|outfit|dressed|look)\b",
                answer,
                re.I,
            ):
                vis["look_asked"] = True

    job = None
    try:
        save_runtime(runtime)
        save_memory(memory)
    except Exception:
        pass
    stopped = jobs.chat_stop_requested(chat_gen)
    jobs.chat_finished(chat_gen)
    try:
        if stopped and not queue_command and not shot_kind:
            job = None
        elif plan.get("hold"):
            job = None
        else:
            job = queue_if_needed(
                profile=profile,
                runtime=runtime,
                user_text=question,
                reply=answer,
                command=queue_command,
                shot_kind=shot_kind or None,
                frame=plan.get("frame"),
            )
        if job:
            save_runtime(runtime)
    except Exception:
        job = None
    debug = {}
    if job:
        debug["image_job"] = job["id"]
        debug["image_status"] = job.get("status")
    _LAST_DEBUG = {**(_LAST_DEBUG or {}), **debug}
    done = {"answer": answer, "debug": debug if debug else {}}
    choices = shot_choice_list(plan.get("ask") if plan.get("hold") else None)
    if choices:
        done["choices"] = choices
    if should_offer_see_this(answer, runtime, plan):
        done["see_this"] = True
        try:
            save_runtime(runtime)
        except Exception:
            pass
    if job:
        done["image_job"] = {
            "id": job["id"],
            "status": job.get("status"),
        }
    done["images_ready"] = images_ready(runtime)
    yield {"event": "done", **done}
