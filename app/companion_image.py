"""Companion image: commands, scene object, opportunity, prompt. No Fooocus UI."""
from __future__ import annotations

import html
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.config_load import ROOT

FOOOCUS_ROOT = ROOT.parent / "2_Image_Generator" / "Fooocus"
CKPT_DIR = FOOOCUS_ROOT / "models" / "checkpoints"
LORA_DIR = FOOOCUS_ROOT / "models" / "loras"
IMAGE_DIR = ROOT / "data" / "companion_images"
OUTPUT_ROOT = ROOT / "data" / "companion_output"


def day_output_dir(when: datetime | None = None) -> Path:
    from app.companion_engine import current_device

    day = (when.date() if when else date.today()).isoformat()
    did = current_device() or "_shared"
    path = OUTPUT_ROOT / did / day
    path.mkdir(parents=True, exist_ok=True)
    return path


def gallery_root() -> Path:
    from app.companion_engine import current_device

    did = current_device() or "_shared"
    return OUTPUT_ROOT / did


def list_gallery(limit: int = 72) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    root = gallery_root()
    if root.exists():
        for path in root.rglob("*.png"):
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            items.append(
                {
                    "filename": path.name,
                    "day": path.parent.name if path.parent != root else "",
                    "ts": mtime,
                }
            )
    items.sort(key=lambda x: float(x.get("ts") or 0), reverse=True)
    seen: set[str] = set()
    out = []
    for item in items:
        name = item["filename"]
        if name in seen:
            continue
        seen.add(name)
        out.append({"filename": name, "day": item.get("day") or ""})
        if len(out) >= max(1, min(120, int(limit))):
            break
    return out


def find_image(name: str) -> Path | None:
    safe = Path(name).name
    if not safe or safe != name or ".." in name:
        return None
    for root in (OUTPUT_ROOT, IMAGE_DIR):
        if not root.exists():
            continue
        direct = root / safe
        if direct.is_file():
            return direct
        for hit in root.rglob(safe):
            if hit.is_file():
                return hit
    return None


def append_day_log(
    images: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
    seconds: float | None = None,
) -> Path:
    payload = payload or {}
    day = day_output_dir()
    log_path = day / "log.json"
    entries: list[dict[str, Any]] = []
    if log_path.is_file():
        try:
            loaded = json.loads(log_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                entries = loaded
        except Exception:
            entries = []
    stamp = datetime.now().strftime("%H:%M:%S")
    for img in images:
        entries.append(
            {
                "file": img.get("filename") or Path(str(img.get("path") or "")).name,
                "time": stamp,
                "seconds": img.get("seconds") if img.get("seconds") is not None else seconds,
                "seed": img.get("seed"),
                "prompt": (payload.get("prompt") or "")[:800],
                "checkpoint": img.get("checkpoint") or payload.get("checkpoint"),
                "width": payload.get("width"),
                "height": payload.get("height"),
            }
        )
    log_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    write_day_html(day, entries)
    return day / "log.html"


def write_day_html(day: Path, entries: list[dict[str, Any]]) -> None:
    rows = []
    for item in reversed(entries):
        name = html.escape(str(item.get("file") or ""))
        prompt = html.escape(str(item.get("prompt") or ""))
        meta = " · ".join(
            str(p)
            for p in (
                item.get("time"),
                f"{item.get('seconds')}s" if item.get("seconds") is not None else None,
                f"seed {item.get('seed')}" if item.get("seed") is not None else None,
                item.get("checkpoint"),
            )
            if p
        )
        rows.append(
            f'<article class="card"><img src="{name}" alt="">{"" if not meta else f"<p class=meta>{html.escape(meta)}</p>"}'
            f"{'' if not prompt else f'<p class=prompt>{prompt}</p>'}</article>"
        )
    title = html.escape(day.name)
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Companion · {title}</title>
<style>
body {{ background:#10080d; color:#f7eee9; font:15px/1.45 system-ui,sans-serif; margin:0; padding:28px; }}
h1 {{ font-weight:500; font-size:22px; }}
.card {{ margin:0 0 28px; max-width:420px; }}
img {{ width:100%; border-radius:14px; display:block; }}
.meta {{ color:#8a6f7a; font-size:12px; margin:8px 0 4px; }}
.prompt {{ color:#d9bdc6; font-size:13px; white-space:pre-wrap; }}
</style></head>
<body>
<h1>{title}</h1>
<p class="meta">{len(entries)} image{"s" if len(entries) != 1 else ""} · local only</p>
{"".join(rows) or "<p class=meta>Nothing generated this day.</p>"}
</body></html>
"""
    (day / "log.html").write_text(doc, encoding="utf-8")

CHECKPOINTS = {
    "anima": "animaPencilXL_v500.safetensors",
    "pony": "ponyDiffusionV6XL.safetensors",
    "juggernaut": "juggernautXL_v8Rundiffusion.safetensors",
}
ACCEL = {
    "none": None,
    "lightning": "sdxl_lightning_4step_lora.safetensors",
    "lcm": "sdxl_lcm_lora.safetensors",
    "hyper": "sdxl_hyper_sd_4step_lora.safetensors",
}
IMAGE_STEP_CHOICES = (4, 8, 16, 30)
IMAGE_STEP_DEFAULT = 8
IMAGE_STEP_LABELS = {
    4: "4 — draft",
    8: "8 — fast",
    16: "16 — balanced",
    30: "30 — quality",
}
IMAGE_UNLOCK_TURNS = 20
USER_SEE_RE = re.compile(
    r"(?:^|\b)(?:show me|send (?:me )?(?:a |another )?(?:pic|picture|photo|selfie)|"
    r"let me see(?: you)?|wanna see(?: you)?|want to see you|"
    r"can i see you|picture of you|send nudes?|"
    r"see your (?:face|body|outfit|hair|legs))\b",
    re.I,
)

CMD_RE = re.compile(
    r"^/(image_test|visualize|image|img|show|prompt)(?:\s+(.*))?$",
    re.I,
)
SLASH_COMMANDS = (
    {"cmd": "/img", "hint": "ask her to send a pic"},
    {"cmd": "/image", "hint": "same as /img"},
    {"cmd": "/show", "hint": "show this moment"},
)

NEG_SAFETY = (
    "watermark, signature, text, logo, extra fingers, extra limbs, "
    "bad anatomy, malformed hands, fused fingers, missing fingers, "
    "mutated hands, poorly drawn hands, extra teeth, deformed teeth, "
    "duplicate, lowres, blurry, worst quality, child, loli, shota, underage"
)
NEG_DEFAULT = (
    "photoreal, photograph, realistic skin pores, 3d render, cgi, " + NEG_SAFETY
)

ANIME_KEY = (
    "anime artwork, key visual, studio anime, vibrant, highly detailed, "
    "cinematic composition, not a photo, not a selfie"
)
ANIME_CHAR = (
    "anime illustration, sharp focus, crisp clean lineart, "
    "detailed eyes, natural lips, five fingers, complete head, not cropped"
)
ANIME_STYLE = ANIME_CHAR

SCENERY_RE = re.compile(
    r"\b(beach|ocean|sea|shore|sky|sunset|sunrise|landscape|scenery|mountain|"
    r"forest|cityscape|horizon|waves|stars|lake|river|clouds|waterfall|"
    r"night sky|milky way)\b",
    re.I,
)
TOGETHER_RE = re.compile(
    r"\b(together|with me|both of us|can we see|we see|see it together|"
    r"come with me)\b",
    re.I,
)
US_RE = re.compile(
    r"\b(us in(?:to)? it|two of us|both of us (?:in|on|at)|we standing|"
    r"include us|standing (?:there|in it))\b",
    re.I,
)
VIEW_RE = re.compile(
    r"\b(the view|just the (?:view|beach|sky|water|place|shore)|scenery only|"
    r"landscape|no people|empty (?:beach|shore|view)|only the (?:view|water|sky))\b",
    re.I,
)
HER_RE = re.compile(
    r"\b(see you|show you|look at you|just you|yourself|looking at you|"
    r"your (?:face|body|outfit|dress|saree|sari|clothes)|"
    r"what you(?:'re| are) wearing)\b",
    re.I,
)
CLOSE_RE = re.compile(
    r"\b(close[- ]?up|selfie|(?:just )?(?:your )?(?:lips|eyes|mouth))\b",
    re.I,
)
NUDE_RE = re.compile(
    r"\b(nude|naked|nudes|no clothes|undressed|stripped|unclothed|bare skin)\b",
    re.I,
)
LEGS_RE = re.compile(
    r"\b(legs?|full body|head to (?:toe|feet)|from head to toe|feet|thighs?)\b",
    re.I,
)
SHORT_VIEW = re.compile(
    r"^(the )?((view|beach|sky|water|place|shore|scenery|landscape))\.?$",
    re.I,
)
SHORT_US = re.compile(r"^(us|we|together|both)(\s+of us)?\.?$", re.I)
SHORT_YOU = re.compile(r"^(just )?(you(rself)?|her|him|them)\.?$", re.I)
PERSON_RE = re.compile(
    r"\b(1girl|1boy|girl|boy|woman|man|lady|guy|chola|person|she|he|her|him|"
    r"bikini|swimsuit|saree|sari|dress|standing|sitting|lying|body|face|"
    r"year old|years old|hourglass|curvy|feeding|sketching)\b",
    re.I,
)

PLACE_RE = re.compile(
    r"\b(rooftop|roof|cafe|coffee shop|kitchen|bedroom|bed|apartment|living room|"
    r"couch|sofa|shower|bathroom|balcony|park|street|rain|beach|car|office|"
    r"studio|library|train|station|bridge|garden|club|bar|window)\b",
    re.I,
)
OUTFIT_RE = re.compile(
    r"\b((?:red|black|white|blue|pink|green|gold|golden|olive|oversized|leather|silk)\s+)?"
    r"(hoodie|jacket|dress|coat|shirt|sweater|skirt|jeans|pajamas|robe|lingerie|"
    r"t-shirt|blouse|kimono|uniform|saree|sari|bikini|micro-bikini|swimsuit|sari)\b",
    re.I,
)
ACTION_RE = re.compile(
    r"\b(sitting|standing|walking|lying|leaning|cooking|studying|gaming|"
    r"sleeping|dancing|kissing|holding|reaching|looking|smiling|crying|"
    r"stretching|running|waiting|waving|feeding|sketching|drawing|painting|"
    r"eating|drinking)\b",
    re.I,
)
LIGHT_RE = re.compile(
    r"\b(sunset|sunrise|golden hour|neon|lamplight|moonlight|morning|"
    r"night|evening|overcast|rainy|warm light|dim)\b",
    re.I,
)
GARMENTS = (
    "hoodie|jacket|dress|coat|shirt|sweater|skirt|jeans|pajamas|robe|"
    "lingerie|t-shirt|tee|blouse|kimono|uniform|saree|sari"
)
REJECT_RE = re.compile(
    rf"\b(?:not a |not the |no more |don'?t wear|dont wear|stop wearing|"
    rf"without (?:the |a )?|hate (?:the |that )?|ditch the |lose the )"
    rf"({GARMENTS})\b",
    re.I,
)
TOO_BAD_RE = re.compile(
    rf"(?:too bad.{{0,60}}\b({GARMENTS})\b|\b({GARMENTS})\b.{{0,24}}too bad)",
    re.I,
)
WEAR_RE = re.compile(
    r"\b(?:wearing|wear|put on|dressed in|change into)\s+"
    r"(.{3,80}?)(?:[.!?\n]|$)",
    re.I,
)
HAIR_RE = re.compile(
    r"\b(?:your|her|his|their)\s+hair\s+(?:is|are)?\s*(.{3,80}?)(?:[.!?\n]|$)"
    r"|\byou have\s+(.{3,60}?)\s+hair\b",
    re.I,
)
EYES_RE = re.compile(
    r"\b(?:your|her|his|their)\s+eyes\s+(?:are|is)?\s*(.{3,60}?)(?:[.!?\n]|$)",
    re.I,
)
LOOK_ASK_RE = re.compile(
    r"\b(hair|wear|look like|picture me|see me|outfit|dressed|look)\b",
    re.I,
)
INVENTED_OUTFITS = frozenset({"oversized hoodie", "simple dark shirt", "casual indoor clothes"})
DIRECTOR_SYS = """You write one anime still for SDXL. JSON only, no markdown.
Keys: location, outfit, action, lighting, camera, rewrite
Use the given kind.
rewrite: 12-30 comma-separated tags. Anime key visual, not a photo.
scenery: environment first, people absent or tiny, wide establishing, no looking at viewer.
together: two adult figures small in frame, often from behind, looking at the place, wide, complete heads.
character: she is the subject. Complete head not cropped. Follow CAMERA. Only hair/clothes from LOOK unless LOOK is nude.
close: face / upper chest if they asked close. Complete head, not cut off.
If LOOK or the wish is nude/naked, outfit must be nude, naked, no clothes. Do not add a shirt, dress, or hoodie.
If they asked legs or full body, camera is full body head-to-feet, legs visible, not a cowboy crop.
Never invent hoodie, hair color, or body. Empty LOOK = omit those tags.
Adults only."""


def _clip_phrase(text: str, n: int = 80) -> str:
    return re.sub(r"\s+", " ", (text or "").strip(" .,;:")).strip()[:n]


def rejected_garments(text: str) -> list[str]:
    found: list[str] = []
    for match in REJECT_RE.finditer(text or ""):
        found.append(match.group(1).lower())
    for match in TOO_BAD_RE.finditer(text or ""):
        word = (match.group(1) or match.group(2) or "").lower()
        if word:
            found.append(word)
    return found


def look_unknown(profile: dict[str, Any]) -> bool:
    vis = _visual(profile)
    card = profile.get("card") or {}
    hair = (vis.get("hair") or "").strip()
    outfit = (vis.get("default_outfit") or "").strip()
    look = (card.get("appearance") or vis.get("look_extra") or "").strip()
    return not (hair or outfit or look)


def persist_visual_card(sets: dict[str, str] | None = None, clears: list[str] | None = None) -> None:
    from app.companion import load_state, save_state

    sets = sets or {}
    clears = clears or []
    if not sets and not clears:
        return
    try:
        state = load_state()
    except Exception:
        return
    card = state.setdefault("card", {})
    dirty = False
    for key, val in sets.items():
        val = (val or "").strip()
        if val and card.get(key) != val:
            card[key] = val
            dirty = True
    for key in clears:
        if card.get(key):
            card[key] = ""
            dirty = True
    if dirty:
        try:
            save_state(state)
        except Exception:
            pass


def learn_look(profile: dict[str, Any], user_text: str, extra: str = "") -> dict[str, Any]:
    blob = " ".join(p for p in (user_text, extra) if p)
    sets: dict[str, str] = {}
    clears: list[str] = []
    vis = _visual(profile)
    dropped = rejected_garments(blob)
    hair = HAIR_RE.search(blob)
    if hair:
        phrase = _clip_phrase(hair.group(1) or hair.group(2) or "")
        if phrase and "hoodie" not in phrase.lower():
            sets["vis_hair"] = phrase if "hair" in phrase.lower() else phrase + " hair"
    eyes = EYES_RE.search(blob)
    if eyes:
        phrase = _clip_phrase(eyes.group(1) or "")
        if phrase:
            sets["vis_eyes"] = phrase if "eye" in phrase.lower() else phrase + " eyes"
    wear = WEAR_RE.search(blob)
    if wear:
        phrase = _clip_phrase(wear.group(1) or "")
        low = phrase.lower()
        if phrase and not any(g in low for g in dropped):
            sets["vis_default_outfit"] = phrase
    outfit_hit = OUTFIT_RE.search(blob)
    if outfit_hit and "vis_default_outfit" not in sets and not dropped:
        if WEAR_RE.search(blob) or re.search(r"\b(?:wear|put on|dressed|change into|in a|in an)\b", blob, re.I):
            sets["vis_default_outfit"] = _clip_phrase(outfit_hit.group(0))
    new_outfit = sets.get("vis_default_outfit") or ""
    if NUDE_RE.search(blob):
        sets.pop("vis_default_outfit", None)
        clears.append("vis_default_outfit")
    if dropped:
        if new_outfit and any(g in new_outfit.lower() for g in dropped):
            sets.pop("vis_default_outfit", None)
            clears.append("vis_default_outfit")
        elif not new_outfit and any(
            g in (vis.get("default_outfit") or "").lower() for g in dropped
        ):
            clears.append("vis_default_outfit")
    return {"sets": sets, "clears": clears}


def apply_visual_intent(text: str, scene: dict[str, str], vis: dict[str, str]) -> dict[str, str]:
    scene = dict(scene)
    blob = text or ""
    dropped = rejected_garments(blob)
    outfit = (scene.get("outfit") or vis.get("default_outfit") or "").lower()
    for garment in dropped:
        if garment in outfit or garment in (scene.get("outfit") or "").lower():
            scene["outfit"] = ""
            scene["drop"] = garment
    if re.search(r"\b(neckline|collarbone|open (?:the )?collar|show (?:your |some )?skin)\b", blob, re.I):
        covering = ("hoodie", "sweater", "coat", "jacket")
        current = (scene.get("outfit") or vis.get("default_outfit") or "").lower()
        if any(g in current for g in covering) or any(g in dropped for g in covering):
            scene["outfit"] = ""
        note = scene.get("user_note") or ""
        if "neckline" not in note.lower():
            scene["user_note"] = ", ".join(p for p in (note, "open neckline, collarbones") if p)
    if NUDE_RE.search(blob):
        scene["outfit"] = "nude, naked, no clothes"
        scene["drop"] = "clothes"
        return scene
    wear = WEAR_RE.search(blob)
    if wear:
        phrase = _clip_phrase(wear.group(1) or "")
        if phrase and not any(g in phrase.lower() for g in dropped):
            scene["outfit"] = phrase
    return scene


def _parse_json_obj(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip().rstrip("`").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def direct_scene(
    profile: dict[str, Any],
    user_text: str,
    reply: str,
    extra: str,
    vis: dict[str, str],
    extra_kind: str = "character",
) -> dict[str, str]:
    from app.llm import chat

    blob = " ".join(p for p in (user_text, extra, reply) if p)
    wearing = "nude, no clothes" if NUDE_RE.search(blob) else vis.get("default_outfit")
    known = ", ".join(
        f"{k}={v}"
        for k, v in (
            ("hair", vis.get("hair")),
            ("eyes", vis.get("eyes")),
            ("wearing", wearing),
            ("look", vis.get("look_extra")),
        )
        if v
    ) or "nothing known — do not invent"
    kind = extra_kind or "character"
    user = (
        f"KIND: {kind}\n"
        f"LOOK: {known}\n"
        f"User: {(user_text or '')[:500]}\n"
        f"Character: {(reply or '')[:500]}\n"
        f"Wish: {(extra or '')[:400]}"
    )
    try:
        raw = chat(
            [
                {"role": "system", "content": DIRECTOR_SYS},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            num_predict=220,
        )
    except Exception:
        return {}
    data = _parse_json_obj(raw)
    out: dict[str, str] = {}
    for key in ("outfit", "location", "action", "expression", "lighting", "camera", "drop", "rewrite"):
        val = data.get(key)
        if isinstance(val, str) and val.strip() and val.strip().lower() not in {"unknown", "none", "n/a"}:
            out[key] = _clip_phrase(val, 400 if key == "rewrite" else 120)
    return out


def pnginfo_from_meta(meta: dict[str, Any]):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    prompt = str(meta.get("prompt") or "")
    negative = str(meta.get("negative") or "")
    params = (
        f"{prompt}\nNegative prompt: {negative}\n"
        f"Steps: {meta.get('steps')}, Sampler: Euler a, CFG scale: {meta.get('cfg')}, "
        f"Seed: {meta.get('seed')}, Size: {meta.get('width')}x{meta.get('height')}, "
        f"Model: {meta.get('checkpoint') or ''}, Accel: {meta.get('accel') or 'none'}"
    )
    info.add_text("parameters", params[:16000])
    for key in ("prompt", "negative", "seed", "steps", "cfg", "width", "height", "accel", "checkpoint", "device"):
        val = meta.get(key)
        if val is not None and str(val):
            info.add_text(key, str(val)[:4000])
    info.add_text("Software", "EduRAG companion")
    return info


def write_image_sidecar(path: Path, meta: dict[str, Any]) -> None:
    """Kept for older tests. Prompt lives in PNG text chunks, log.html is the diary."""
    del path, meta
    return


def default_visual(gender: str = "woman") -> dict[str, str]:
    """No wardrobe or face invented here. Safety age lock only."""
    adult = "adult man" if gender == "man" else "adult woman"
    return {
        "hair": "",
        "eyes": "",
        "skin": "",
        "face": "",
        "body": adult,
        "distinctive": "",
        "default_outfit": "",
        "art_style": "",
    }


def default_image_settings() -> dict[str, Any]:
    return {
        "image_mode": "manual",
        "image_checkpoint": CHECKPOINTS["anima"],
        "image_width": 768,
        "image_height": 1152,
        "image_steps": IMAGE_STEP_DEFAULT,
        "image_cfg": 4.0,
        "image_sampler": "dpmpp_2m",
        "image_seed": -1,
        "image_negative": NEG_DEFAULT,
        "image_cooldown_sec": 90,
        "image_max_auto": 4,
        "image_count": 1,
        "image_accel": "none",
        "image_variations": False,
    }


def parse_command(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    match = CMD_RE.match(raw)
    if not match:
        return None
    name = match.group(1).lower()
    rest = (match.group(2) or "").strip()
    count = 1
    extra = rest
    if rest:
        bits = rest.split(None, 1)
        if bits[0].isdigit():
            count = max(1, min(3, int(bits[0])))
            extra = bits[1] if len(bits) > 1 else ""
    kind = "test" if name == "image_test" else ("prompt" if name == "prompt" else "manual")
    return {"kind": kind, "count": count, "extra": extra, "raw": raw, "name": name}


def detect_user_image_ask(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw or parse_command(raw):
        return None
    if not USER_SEE_RE.search(raw):
        return None
    extra = USER_SEE_RE.sub("", raw).strip(" ,.-")
    return {"kind": "manual", "count": 1, "extra": extra, "raw": raw, "name": "ask"}


def images_ready(runtime: dict[str, Any] | None) -> bool:
    runtime = runtime or {}
    if runtime.get("images_unlocked"):
        return True
    if int(runtime.get("turns") or 0) >= IMAGE_UNLOCK_TURNS:
        return True
    try:
        from app.companion_engine import load_chat

        if len(load_chat()) >= IMAGE_UNLOCK_TURNS:
            return True
    except Exception:
        pass
    return False


SEE_THIS_RE = re.compile(
    r"(?:\*[^*]{8,}\*|\[I[^\]]{8,}\]|"
    r"\b(?:wearing|unbutton|fabric|t-shirt|collarbone|leaning|"
    r"kiss(?:ing|ed)?|lips|thighs|legs|saree|hoodie|dress)\b)",
    re.I,
)


def should_offer_see_this(answer: str, runtime: dict[str, Any] | None, plan: dict[str, Any] | None) -> bool:
    runtime = runtime or {}
    plan = plan or {}
    if not images_ready(runtime):
        return False
    if plan.get("hold") or plan.get("locked"):
        return False
    text = (answer or "").strip()
    if len(text) < 48:
        return False
    if not SEE_THIS_RE.search(text):
        return False
    turns = int(runtime.get("turns") or 0)
    last = int(runtime.get("last_see_turn") or 0)
    if last and turns - last < 8:
        return False
    runtime["last_see_turn"] = turns
    return True


def mark_image_unlock(runtime: dict[str, Any]) -> dict[str, Any]:
    if int(runtime.get("turns") or 0) >= IMAGE_UNLOCK_TURNS:
        runtime["images_unlocked"] = True
    return runtime


def should_offer_picture(
    runtime: dict[str, Any] | None,
    *,
    reply: str = "",
    user_text: str = "",
) -> bool:
    runtime = runtime or {}
    if not images_ready(runtime):
        return False
    vis = runtime.get("visual") if isinstance(runtime.get("visual"), dict) else {}
    last = float(vis.get("last_offer_ts") or 0)
    if last and time.time() - last < 90:
        return False
    last_turn = int(vis.get("last_offer_turn") or 0)
    turns = int(runtime.get("turns") or 0)
    if last_turn and turns - last_turn < 4:
        return False
    blob = f"{user_text} {reply}".lower()
    if USER_SEE_RE.search(blob):
        return True
    if any(w in blob for w in ("look at me", "this dress", "this outfit", "right now", "in this")):
        return True
    if ACTION_RE.search(blob) and (PLACE_RE.search(blob) or WEAR_RE.search(blob)):
        return True
    return len((reply or "").strip()) > 80


def note_picture_offer(runtime: dict[str, Any]) -> None:
    vis = runtime.setdefault("visual", {})
    vis["last_offer_ts"] = time.time()
    vis["last_offer_turn"] = int(runtime.get("turns") or 0)


def slash_commands() -> list[dict[str, str]]:
    return [dict(item) for item in SLASH_COMMANDS]


def detect_style(text: str) -> str:
    t = text or ""
    if re.search(
        r"\b(photo(?:real(?:istic)?|graph)?|dslr|35mm|raw photo|photoreal|realistic skin)\b",
        t,
        re.I,
    ):
        return "photoreal"
    if re.search(r"\b(sketch|pencil|charcoal|doodle|line art|lineart|gestural)\b", t, re.I):
        return "sketch"
    if re.search(r"\b(watercolor|gouache|ink wash)\b", t, re.I):
        return "watercolor"
    if re.search(r"\b(oil paint|oil painting|impasto|on canvas)\b", t, re.I):
        return "oil"
    if re.search(r"\b(manga|manhwa|comic panel|screentone)\b", t, re.I):
        return "manga"
    if re.search(r"\b(anime|studio ghibli|key visual)\b", t, re.I):
        return "anime"
    return "follow"


def detect_frame(text: str, kind: str = "") -> str:
    t = text or ""
    if re.search(
        r"\b(landscape|widescreen|wide shot|panorama|establishing|16:9|cinemascope|panavision)\b",
        t,
        re.I,
    ):
        return "landscape"
    if re.search(r"\b(portrait|vertical|9:16|full body|cowboy shot|close[- ]?up)\b", t, re.I):
        return "portrait"
    if (kind or "") in {"scenery", "together"}:
        return "landscape"
    return "portrait"


def classify_frame_answer(text: str) -> str:
    t = (text or "").strip().lower()
    if t in {"portrait", "vertical", "tall"} or re.match(r"^portrait\b", t):
        return "portrait"
    if t in {"landscape", "wide", "horizontal"} or re.match(r"^landscape\b", t):
        return "landscape"
    if t in {"original", "as written", "as-written"} or re.search(
        r"\b(as written|as (?:i |the )?prompt|keep it)\b", t
    ):
        return "original"
    return ""


def classify_angle_answer(text: str) -> str:
    t = (text or "").strip().lower()
    if t in {"close", "selfie", "face", "closeup", "close-up"} or re.match(r"^close\b", t):
        return "close"
    if t in {"body", "full", "full body", "legs", "feet"} or re.search(
        r"\b(full body|head to toe|legs|from head to toe)\b", t
    ):
        return "body"
    if t in {"original", "skip", "as written", "as-written"} or re.search(
        r"\b(as written|skip|just (?:send|draw|go))\b", t
    ):
        return "original"
    return ""


def style_bits(style: str) -> tuple[str, str]:
    style = (style or "follow").lower()
    if style == "photoreal":
        return (
            "photorealistic, natural lighting, detailed",
            "anime, cartoon, drawing, illustration, cgi",
        )
    if style == "sketch":
        return (
            "pencil sketch, paper texture, loose lines, hatching",
            "photoreal, photograph, 3d render, cgi",
        )
    if style == "watercolor":
        return (
            "watercolor painting, soft pigments, paper grain",
            "photoreal, photograph, 3d render, cgi",
        )
    if style == "oil":
        return (
            "oil painting, visible brushstrokes, canvas",
            "photoreal, photograph, 3d render, cgi",
        )
    if style == "manga":
        return (
            "manga, manga panel, screentones, crisp ink",
            "photoreal, photograph, 3d render, cgi",
        )
    if style == "anime":
        return (ANIME_CHAR, "photoreal, photograph, realistic skin pores, 3d render, cgi")
    return ("", "child, loli, shota, underage")


def shot_size(kind: str, frame: str = "", extra: str = "") -> tuple[int, int]:
    resolved = (frame or "").lower()
    if resolved in {"original", "as_written", "as-written", ""}:
        resolved = detect_frame(extra, kind)
    if resolved == "landscape":
        return 1152, 768
    return 768, 1152


def classify_kind(text: str) -> str:
    blob = text or ""
    if CLOSE_RE.search(blob):
        return "close"
    if US_RE.search(blob):
        return "together"
    if VIEW_RE.search(blob):
        return "scenery"
    if TOGETHER_RE.search(blob):
        return ""
    if HER_RE.search(blob):
        return "character"
    if WEAR_RE.search(blob) or (
        OUTFIT_RE.search(blob) and re.search(r"\b(wear|put on|dressed|saree|sari)\b", blob, re.I)
    ):
        return "character"
    if SCENERY_RE.search(blob) and not ACTION_RE.search(blob) and not HER_RE.search(blob):
        return "scenery"
    if ACTION_RE.search(blob) and (PLACE_RE.search(blob) or SCENERY_RE.search(blob)):
        return "character"
    return ""


def classify_answer(text: str) -> str:
    t = (text or "").strip()
    if SHORT_VIEW.match(t) or VIEW_RE.search(t):
        return "scenery"
    if SHORT_US.match(t) or US_RE.search(t):
        return "together"
    if SHORT_YOU.match(t) or HER_RE.search(t):
        return "character"
    if CLOSE_RE.search(t):
        return "close"
    return classify_kind(t)


def infer_kind(text: str) -> str:
    blob = text or ""
    kind = classify_kind(blob)
    if kind:
        return kind
    if VIEW_RE.search(blob) or re.search(r"\bno people\b", blob, re.I):
        return "scenery"
    if PERSON_RE.search(blob) or WEAR_RE.search(blob) or OUTFIT_RE.search(blob):
        return "character"
    if ACTION_RE.search(blob) and re.search(r"\b(you|me|your)\b", blob, re.I):
        return "character"
    return ""


def _hold_angle(kind: str, extra: str, raw: str) -> dict[str, Any]:
    kind = kind or "character"
    return {
        "hold": True,
        "ask": "angle",
        "kind": kind,
        "extra": extra,
        "pending": {
            "asked": "angle",
            "extra": extra,
            "kind": kind,
            "user_text": raw,
        },
    }


def prepare_image_turn(
    *,
    profile: dict[str, Any],
    runtime: dict[str, Any],
    user_text: str,
    command: dict[str, Any] | None,
) -> dict[str, Any]:
    pending = dict(runtime.get("pending_image") or {})
    extra = (command or {}).get("extra") or ""
    raw = (user_text or "").strip()
    cmd_kind = (command or {}).get("kind") or ""
    last = dict(runtime.get("last_shot") or {})

    if cmd_kind == "test":
        return {"hold": False, "kind": "character", "extra": extra, "ask": None, "pending": {}}

    button = bool(command) and not extra and raw.lower() in {"/image", "/img", "/show", "/visualize", "/prompt", ""}
    if button:
        return {
            "hold": True,
            "ask": "angle",
            "kind": "character",
            "extra": last.get("extra") or "",
            "pending": {
                "asked": "angle",
                "extra": last.get("extra") or "",
                "kind": "character",
                "user_text": raw,
            },
        }

    if pending.get("asked") == "angle" and not command:
        picked = classify_angle_answer(raw)
        if not picked:
            return {
                "hold": True,
                "ask": "angle",
                "keep": True,
                "kind": pending.get("kind") or "character",
                "extra": pending.get("extra") or "",
                "pending": pending,
            }
        return {
            "hold": False,
            "kind": "close" if picked == "close" else (pending.get("kind") or "character"),
            "extra": pending.get("extra") or "",
            "ask": None,
            "pending": {},
            "frame": picked,
            "literal": True,
            "synthetic": True,
            "command": {
                "kind": "manual",
                "count": 1,
                "extra": pending.get("extra") or pending.get("reply") or "",
            },
        }

    blob = " ".join(p for p in (raw, extra) if p)
    kind = ""
    merged_extra = extra

    if pending.get("asked") == "frame" and not command:
        frame = classify_frame_answer(raw)
        if not frame:
            return {
                "hold": True,
                "ask": "frame",
                "keep": True,
                "kind": pending.get("kind") or "",
                "extra": pending.get("extra") or "",
                "pending": pending,
            }
        return {
            "hold": False,
            "kind": pending.get("kind") or infer_kind(pending.get("extra") or "") or "character",
            "extra": pending.get("extra") or "",
            "ask": None,
            "pending": {},
            "literal": bool(pending.get("literal")),
            "frame": frame,
            "style": pending.get("style") or detect_style(pending.get("extra") or ""),
            "synthetic": True,
            "command": {
                "kind": "prompt" if pending.get("literal") else "manual",
                "count": 1,
                "extra": pending.get("extra") or "",
            },
        }

    if pending.get("asked") == "shot" and not command:
        kind = classify_answer(raw)
        merged_extra = " ".join(p for p in (pending.get("extra"), extra, raw) if p)
        if not kind:
            return {
                "hold": True,
                "ask": "shot",
                "keep": True,
                "kind": "",
                "extra": pending.get("extra") or "",
                "pending": pending,
            }
        return {
            "hold": False,
            "kind": kind,
            "extra": merged_extra,
            "ask": None,
            "pending": {},
            "synthetic": True,
            "command": {"kind": "manual", "count": 1, "extra": merged_extra},
        }

    if cmd_kind == "prompt" and extra.strip():
        extra = extra.strip()
        kind = infer_kind(extra) or infer_kind(blob) or "character"
        if kind in {"character", "close"} and look_unknown(profile):
            return {
                "hold": True,
                "ask": "look",
                "kind": kind,
                "extra": extra,
                "pending": {"asked": "look", "extra": extra, "kind": kind, "user_text": raw},
            }
        if kind in {"character", "close"}:
            return _hold_angle(kind, extra, raw)
        return {
            "hold": False,
            "kind": kind,
            "extra": extra,
            "ask": None,
            "pending": {},
            "literal": True,
            "synthetic": True,
            "command": {"kind": "manual", "count": max(1, int((command or {}).get("count") or 1)), "extra": extra},
        }

    if command:
        kind = infer_kind(blob)
        if extra.strip():
            if not kind or (TOGETHER_RE.search(blob) and kind == "character"):
                return {
                    "hold": True,
                    "ask": "shot",
                    "kind": "",
                    "extra": extra,
                    "pending": {"asked": "shot", "extra": extra, "user_text": raw},
                }
            if kind in {"character", "close"} and look_unknown(profile):
                return {
                    "hold": True,
                    "ask": "look",
                    "kind": kind,
                    "extra": extra,
                    "pending": {"asked": "look", "extra": extra, "kind": kind, "user_text": raw},
                }
            if kind in {"character", "close"}:
                return _hold_angle(kind, extra, raw)
            return {
                "hold": False,
                "kind": kind,
                "extra": extra,
                "ask": None,
                "pending": {},
                "literal": True,
                "synthetic": True,
                "command": {"kind": "manual", "count": max(1, int((command or {}).get("count") or 1)), "extra": extra},
            }
        if not kind:
            return _hold_angle("character", extra, raw)
        if kind in {"character", "close"} and look_unknown(profile):
            return {
                "hold": True,
                "ask": "look",
                "kind": kind,
                "extra": extra,
                "pending": {"asked": "look", "extra": extra, "kind": kind, "user_text": raw},
            }
        if kind in {"character", "close"}:
            return _hold_angle(kind, extra, raw)
        return {
            "hold": False,
            "kind": kind,
            "extra": extra,
            "ask": None,
            "pending": {},
            "synthetic": True,
            "command": {"kind": "manual", "count": 1, "extra": extra},
        }

    return {"hold": False, "kind": "", "extra": extra, "ask": None, "pending": None, "skip": True}


def shot_choice_list(ask: str | None) -> list[dict[str, str]]:
    if ask == "shot":
        return [
            {"id": "scenery", "label": "The view"},
            {"id": "together", "label": "Us in it"},
            {"id": "character", "label": "You"},
        ]
    if ask == "angle":
        return [
            {"id": "close", "label": "Close"},
            {"id": "body", "label": "Full body"},
            {"id": "original", "label": "As written"},
        ]
    if ask == "frame":
        return [
            {"id": "portrait", "label": "Portrait"},
            {"id": "landscape", "label": "Landscape"},
            {"id": "original", "label": "As written"},
        ]
    if ask == "see":
        return [{"id": "see_this", "label": "see this"}]
    return []


def apply_shot_choice(
    *,
    profile: dict[str, Any],
    runtime: dict[str, Any],
    choice_id: str,
) -> dict[str, Any] | None:
    pending = dict(runtime.get("pending_image") or {})
    extra = pending.get("extra") or ""
    kind = (choice_id or "").strip().lower()
    if kind == "see_this":
        extra = extra or pending.get("reply") or ""
        shot_kind = pending.get("kind") or infer_kind(extra) or "character"
        runtime["pending_image"] = {
            "asked": "angle",
            "extra": extra,
            "kind": shot_kind,
            "user_text": extra,
            "reply": extra,
        }
        return None
    if kind in {"close", "body", "original"} and pending.get("asked") == "angle":
        extra = extra or pending.get("reply") or ""
        shot_kind = "close" if kind == "close" else (pending.get("kind") or infer_kind(extra) or "character")
        runtime["pending_image"] = {}
        cmd = {"kind": "manual", "count": 1, "extra": extra}
        return queue_if_needed(
            profile=profile,
            runtime=runtime,
            user_text=extra or kind,
            reply="",
            command=cmd,
            shot_kind=shot_kind,
            frame=kind,
        )
    if kind in {"portrait", "landscape", "original"}:
        shot_kind = pending.get("kind") or infer_kind(extra) or "character"
        runtime["pending_image"] = {}
        cmd = {
            "kind": "prompt" if pending.get("literal") else "manual",
            "count": 1,
            "extra": extra,
        }
        return queue_if_needed(
            profile=profile,
            runtime=runtime,
            user_text=extra or kind,
            reply="",
            command=cmd,
            shot_kind=shot_kind,
            frame=kind,
        )
    if kind not in {"scenery", "together", "character", "close"}:
        return None
    runtime["pending_image"] = {}
    cmd = {"kind": "manual", "count": 1, "extra": extra}
    return queue_if_needed(
        profile=profile,
        runtime=runtime,
        user_text=extra or kind,
        reply="",
        command=cmd,
        shot_kind=kind,
    )


def _visual(profile: dict[str, Any]) -> dict[str, str]:
    gender = (profile.get("partner_gender") or "woman").lower()
    base = default_visual(gender if gender in {"man", "woman"} else "woman")
    card = profile.get("card") or {}
    for key in list(base.keys()):
        val = (card.get("vis_" + key) or "").strip()
        if val:
            base[key] = val
    look = (card.get("appearance") or "").strip()
    if look:
        base["look_extra"] = look
    return base


def extract_scene(
    user_text: str,
    reply: str,
    runtime: dict[str, Any],
    extra: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, str]:
    blob = " ".join(p for p in (user_text, reply, extra) if p)
    inter = runtime.get("interaction") or {}
    emo = runtime.get("emotion") or {}
    kept = dict(runtime.get("visual") or {})
    asked = bool(kept.get("look_asked"))
    visual: dict[str, str] = {}
    if asked:
        visual["look_asked"] = "1"
    vis = _visual(profile or {})
    place = PLACE_RE.search(blob)
    if place:
        visual["location"] = place.group(0).lower()
    else:
        scene = (inter.get("current_scene") or "")
        hit = PLACE_RE.search(scene)
        if hit:
            visual["location"] = hit.group(0).lower()
        elif (kept.get("location") or "") not in {"", "quiet indoor room"}:
            visual["location"] = kept["location"]
    dropped = rejected_garments(blob)
    if NUDE_RE.search(blob):
        visual["outfit"] = "nude, naked, no clothes"
        visual["drop"] = "clothes"
    else:
        outfit = OUTFIT_RE.search(blob)
        sticky = (kept.get("outfit") or "").strip()
        known = (vis.get("default_outfit") or "").strip()
        if outfit and not any(g in outfit.group(0).lower() for g in dropped):
            if WEAR_RE.search(blob) or re.search(r"\b(?:wear|put on|dressed|change into)\b", blob, re.I):
                visual["outfit"] = outfit.group(0).lower()
            elif extra and outfit.group(0).lower() in extra.lower():
                visual["outfit"] = outfit.group(0).lower()
        if not visual.get("outfit"):
            if sticky and sticky.lower() not in INVENTED_OUTFITS:
                if not any(g in sticky.lower() for g in dropped):
                    if sticky.lower() in known.lower() or sticky.lower() in blob.lower():
                        visual["outfit"] = sticky
            if not visual.get("outfit") and known and known.lower() not in INVENTED_OUTFITS:
                if not any(g in known.lower() for g in dropped):
                    visual["outfit"] = known
    action = ACTION_RE.search(blob)
    light = LIGHT_RE.search(blob)
    if action:
        visual["action"] = action.group(0).lower()
    elif kept.get("action"):
        visual["action"] = kept["action"]
    if light:
        visual["lighting"] = light.group(0).lower()
    elif kept.get("lighting"):
        visual["lighting"] = kept["lighting"]
    visual["mood"] = (emo.get("primary") or inter.get("mood") or "at ease")
    visual["expression"] = _expression(visual["mood"], blob)
    if extra:
        visual["user_note"] = extra[:200]
    visual["time"] = _time_of_day(blob, visual.get("lighting") or "")
    visual = apply_visual_intent(blob, visual, vis)
    return visual


def _expression(mood: str, blob: str) -> str:
    low = (blob + " " + mood).lower()
    if any(w in low for w in ("wanting", "kiss", "flirt", "smirk", "playful")):
        return "playful, slightly flushed"
    if any(w in low for w in ("hurt", "sad", "tired", "tender")):
        return "soft, tired, gentle eyes"
    if any(w in low for w in ("angry", "bristling", "frustrated")):
        return "sharp gaze, tense mouth"
    if "amused" in low:
        return "amused, one brow slightly raised"
    return "calm, present, looking toward the viewer"


def _time_of_day(blob: str, lighting: str) -> str:
    low = (blob + " " + lighting).lower()
    if "sunset" in low or "golden" in low:
        return "sunset"
    if "morning" in low or "sunrise" in low:
        return "morning"
    if "night" in low or "moon" in low:
        return "night"
    if "evening" in low:
        return "evening"
    return "indoor evening"


def opportunity_score(
    *,
    mode: str,
    command: dict[str, Any] | None,
    scene: dict[str, str],
    prev: dict[str, str] | None,
    last_ts: float,
    auto_count: int,
    cooldown: int,
    max_auto: int,
    user_text: str,
    reply: str,
) -> tuple[float, str]:
    if command:
        return 100.0, "explicit request"
    mode = (mode or "manual").lower()
    if mode in {"off", "manual"}:
        return 0.0, "mode " + mode
    now = time.time()
    if last_ts and now - last_ts < max(15, int(cooldown or 90)):
        return 0.0, "cooldown"
    if auto_count >= max(0, int(max_auto or 4)):
        return 0.0, "session cap"
    score = 8.0
    reason = "small talk"
    prev = prev or {}
    loc = (scene.get("location") or "").lower()
    if loc and loc != (prev.get("location") or "").lower() and loc not in {"quiet indoor room", ""}:
        score = max(score, 78.0)
        reason = "scene change"
    outfit = (scene.get("outfit") or "").lower()
    if outfit and outfit != (prev.get("outfit") or "").lower():
        score = max(score, 72.0)
        reason = "outfit change"
    blob = (user_text + " " + reply).lower()
    if any(w in blob for w in ("look at", "look at me", "what i'm wearing", "what i am wearing", "show you")):
        score = max(score, 80.0)
        reason = "show moment"
    if ACTION_RE.search(blob) and PLACE_RE.search(blob):
        score = max(score, 58.0)
        reason = "visual action"
    if any(w in blob for w in ("rooftop", "sunset", "rain", "cafe", "walk")):
        score = max(score, 52.0)
        reason = "interesting place"
    thresholds = {"rare": 70.0, "occasional": 50.0, "frequent": 34.0}
    need = thresholds.get(mode, 99.0)
    if score < need:
        return score, f"below {mode} threshold ({score:.0f}<{need:.0f})"
    return score, reason


def scene_caption(text: str, limit: int = 320) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    parts = [p.strip(" .") for p in re.split(r",", raw) if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = part.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(part)
    joined = ", ".join(out) if out else raw
    return joined[:limit]


def build_prompts(
    profile: dict[str, Any],
    scene: dict[str, str],
    *,
    variation: int = 0,
    kind: str = "",
) -> tuple[str, str]:
    vis = _visual(profile)
    name = (profile.get("name") or "Maya").strip()
    gender = (profile.get("partner_gender") or "woman").lower()
    kind = (kind or scene.get("kind") or "character").lower()
    who = "1girl, adult" if gender != "man" else "1boy, adult"
    identity_bits = [
        vis.get("hair"),
        vis.get("eyes"),
        vis.get("skin"),
        vis.get("face"),
        vis.get("body"),
        vis.get("distinctive"),
        vis.get("look_extra"),
    ]
    outfit = (scene.get("outfit") or vis.get("default_outfit") or "").strip()
    if outfit.lower() in INVENTED_OUTFITS:
        outfit = ""
    rewrite = (scene.get("rewrite") or "").strip()
    loc = (scene.get("location") or "").strip()
    lighting = (scene.get("lighting") or "").strip()
    expression = (scene.get("expression") or "").strip()
    action = (scene.get("action") or "").strip()
    note = (scene.get("user_note") or "").strip()
    style = (scene.get("style") or detect_style(" ".join(p for p in (rewrite, note, action) if p))).lower()
    frame = (scene.get("frame") or "").lower()
    blob_all = " ".join(p for p in (outfit, rewrite, note, loc, action, frame) if p)
    nude = bool(NUDE_RE.search(blob_all) or (scene.get("drop") or "") == "clothes")
    if nude:
        outfit = "nude, naked, no clothes, bare skin"
    wants_legs = frame == "body" or bool(LEGS_RE.search(blob_all))
    style_pos, style_neg = style_bits(style)
    stored_neg = (profile.get("generation") or {}).get("image_negative") or ""
    neg = NEG_SAFETY
    if stored_neg and stored_neg != NEG_DEFAULT:
        neg = stored_neg
    if style_neg:
        neg = neg + ", " + style_neg
    if nude:
        neg = neg + ", clothes, clothing, dressed, shirt, pants, dress, bra, underwear, covered"
    extra_neg = "cropped head"
    if kind == "scenery":
        extra_neg = "selfie, cropped head"
    if style == "photoreal":
        extra_neg = extra_neg + ", extra fingers"
    elif style in {"anime", "manga", "follow"}:
        extra_neg = extra_neg + ", photoreal"

    def _camera() -> str:
        if wants_legs or frame == "body":
            return (
                "full body, head to feet, entire legs visible, standing, "
                "complete head, not cropped at the thighs"
            )
        if frame == "portrait":
            return "portrait orientation, vertical composition, complete head, not cropped"
        if frame == "landscape":
            return "landscape orientation, wide composition"
        if frame in {"original", "as_written"}:
            return "full body, head to feet, legs visible" if wants_legs else ""
        if kind == "scenery":
            return "wide establishing shot"
        if kind == "together":
            return "wide shot, two adult figures, complete heads, not a selfie"
        if kind == "close" or frame == "close":
            return "close-up, complete head, not cropped"
        angles = (
            "complete head, not cropped",
            "three-quarter view, complete head, not cropped",
            "upper body, complete head, not cropped",
        )
        return angles[variation % 3]

    if (scene.get("literal") or "").strip() and rewrite:
        identity = ", ".join(p for p in (who, "adult", *identity_bits) if p) if kind != "scenery" else "adult"
        prompt = ", ".join(p for p in (identity, rewrite, outfit if nude else "", loc, style_pos, _camera()) if p)
        if kind == "scenery":
            neg = neg + ", " + extra_neg
        elif gender != "man":
            neg = neg + ", 1boy, " + extra_neg
        else:
            neg = neg + ", 1girl, " + extra_neg
        return prompt, neg

    if kind == "scenery":
        camera = (scene.get("camera") or _camera() or "wide establishing shot").strip()
        look = style_pos or ANIME_KEY
        prompt = ", ".join(
            p
            for p in (
                rewrite,
                loc,
                lighting,
                action,
                camera,
                note,
                look,
            )
            if p
        )
        neg = neg + ", " + extra_neg + ", 1girl, 1boy"
        return prompt, neg

    if kind == "together":
        camera = (scene.get("camera") or _camera()).strip()
        look = style_pos or ANIME_KEY
        prompt = ", ".join(
            p
            for p in (
                rewrite,
                "two adults",
                loc,
                lighting,
                action,
                camera,
                note,
                look,
            )
            if p
        )
        neg = neg + ", " + extra_neg + ", portrait selfie"
        return prompt, neg

    identity = ", ".join(p for p in (who, *identity_bits) if p)
    camera = (scene.get("camera") or _camera()).strip()
    look = style_pos or (ANIME_CHAR if style in {"anime", "follow", ""} else "")
    prompt = ", ".join(
        p
        for p in (
            identity,
            f"{name}" if name else "",
            outfit,
            action,
            expression,
            loc,
            lighting,
            scene.get("time") or "",
            camera,
            rewrite,
            note,
            look,
        )
        if p
    )
    if gender != "man":
        neg = neg + ", 1boy, " + extra_neg
    else:
        neg = neg + ", 1girl, " + extra_neg
    return prompt, neg


def compact_visual_memory(scene: dict[str, str]) -> str:
    bits = [
        scene.get("last_picture") or scene.get("rewrite"),
        scene.get("location"),
        scene.get("outfit"),
        scene.get("action"),
    ]
    return "Last picture: " + scene_caption(", ".join(b for b in bits if b), 280)


def queue_if_needed(
    *,
    profile: dict[str, Any],
    runtime: dict[str, Any],
    user_text: str,
    reply: str,
    command: dict[str, Any] | None,
    shot_kind: str | None = None,
    frame: str | None = None,
) -> dict[str, Any] | None:
    from app import companion_jobs as jobs
    from app.companion_engine import current_device

    gen = profile.get("generation") or {}
    if not images_ready(runtime):
        return None
    kind = (shot_kind or "").strip()
    extra = (command or {}).get("extra") or ""
    mode = (gen.get("image_mode") or "manual").lower()
    meta = jobs.last_image_meta()
    if command and not kind:
        plan = prepare_image_turn(
            profile=profile, runtime=runtime, user_text=user_text, command=command
        )
        if plan.get("hold") or plan.get("skip"):
            if plan.get("pending") is not None:
                runtime["pending_image"] = plan.get("pending") or {}
            return None
        kind = plan.get("kind") or "character"
        extra = plan.get("extra") or extra
        if plan.get("pending") is not None:
            runtime["pending_image"] = plan.get("pending") or {}
    scene = extract_scene(
        user_text,
        reply,
        runtime,
        extra,
        profile,
    )
    if kind:
        scene["kind"] = kind
    if frame:
        scene["frame"] = str(frame).lower()
    elif LEGS_RE.search(" ".join(p for p in (user_text, extra, reply) if p)):
        scene["frame"] = "body"
    runtime["visual"] = scene
    score, reason = opportunity_score(
        mode=mode,
        command=command,
        scene=scene,
        prev=meta.get("last_scene"),
        last_ts=float(meta.get("last_ts") or 0),
        auto_count=int(meta.get("auto_count") or 0),
        cooldown=int(gen.get("image_cooldown_sec") or 90),
        max_auto=int(gen.get("image_max_auto") or 4),
        user_text=user_text,
        reply=reply,
    )
    if score <= 0:
        return None
    if not kind:
        kind = classify_kind(" ".join(p for p in (user_text, extra, reply) if p)) or "character"
        scene["kind"] = kind
    vis = _visual(profile)
    scene["style"] = detect_style(" ".join(p for p in (user_text, extra) if p))
    scene["frame"] = (frame or scene.get("frame") or detect_frame(extra, kind)).lower()
    literal = bool(extra.strip()) or bool(command and command.get("kind") == "prompt") or bool(scene.get("literal"))
    if literal and extra.strip():
        scene["rewrite"] = extra.strip()
        scene["literal"] = "1"
        scene["kind"] = kind
        directed = {}
    else:
        directed = direct_scene(profile, user_text, reply, extra, vis, extra_kind=kind)
    user_blob = " ".join(p for p in (user_text, extra) if p)
    dropped = rejected_garments(user_blob)
    if NUDE_RE.search(user_blob):
        scene["outfit"] = "nude, naked, no clothes"
        scene["drop"] = "clothes"
        positive_clothes = False
    else:
        positive_clothes = bool(
            WEAR_RE.search(user_blob)
            or (OUTFIT_RE.search(user_blob) and not dropped)
            or (vis.get("default_outfit") or "").strip()
        )
    if directed:
        drop = (directed.get("drop") or "").lower()
        for key in ("outfit", "location", "action", "expression", "lighting", "camera", "rewrite"):
            val = (directed.get(key) or "").strip()
            if not val:
                continue
            if key == "outfit":
                low = val.lower()
                if low in INVENTED_OUTFITS or any(g in low for g in dropped):
                    continue
                if not positive_clothes and kind in {"character", "close"}:
                    continue
            scene[key] = val
        if drop:
            scene["drop"] = drop
            if drop in (scene.get("outfit") or "").lower():
                scene["outfit"] = ""
        scene = apply_visual_intent(user_blob, scene, vis)
        scene["kind"] = kind
        if scene.get("rewrite"):
            scene["rewrite"] = scene_caption(str(scene.get("rewrite") or ""), 280)
        runtime["visual"] = scene
    count = 1
    if command:
        count = int(command.get("count") or 1)
    elif gen.get("image_variations"):
        count = min(3, max(1, int(gen.get("image_count") or 1)))
    prompt, negative = build_prompts(profile, scene, variation=0, kind=kind)
    width, height = shot_size(kind, frame=str(scene.get("frame") or ""), extra=extra)
    run = resolve_image_run(gen)
    accel = run["accel"]
    steps = run["steps"]
    cfg = run["cfg"]
    runtime["pending_image"] = {}
    runtime["last_shot"] = {"kind": kind, "extra": extra, "frame": scene.get("frame"), "style": scene.get("style")}
    caption = scene_caption(extra or scene.get("rewrite") or "")
    vis_rt = runtime.setdefault("visual", {})
    vis_rt["last_picture"] = caption
    vis_rt["last_style"] = scene.get("style") or ""
    if scene.get("rewrite"):
        scene["rewrite"] = scene_caption(str(scene.get("rewrite") or ""), 400)
    jobs_device = current_device()
    ckpt = gen.get("image_checkpoint")
    job = jobs.enqueue(
        {
            "prompt": prompt,
            "negative": negative,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "seed": int(gen.get("image_seed") or -1),
            "count": count,
            "checkpoint": ckpt,
            "accel": accel,
            "scene": scene,
            "manual": bool(command),
            "device_id": jobs_device,
            "caption": caption,
            "debug": {
                "score": score,
                "reason": reason,
                "mode": mode,
                "kind": kind,
                "scene": scene,
                "directed": directed,
            },
        }
    )
    return job


def checkpoint_path(name: str | None) -> Any:
    from pathlib import Path

    filename = name or CHECKPOINTS["anima"]
    path = CKPT_DIR / filename
    if not path.is_file():
        path = CKPT_DIR / CHECKPOINTS["anima"]
    return path


def lora_path(accel: str | None) -> Any:
    from pathlib import Path

    key = (accel or "none").lower()
    filename = ACCEL.get(key)
    if not filename:
        return None
    path = LORA_DIR / filename
    return path if path.is_file() else None


def snap_image_steps(raw: Any) -> int:
    try:
        n = int(float(raw))
    except (TypeError, ValueError):
        n = IMAGE_STEP_DEFAULT
    return min(IMAGE_STEP_CHOICES, key=lambda choice: abs(choice - n))


def suggested_accel(steps: int) -> str:
    if steps <= 4:
        return "lightning" if lora_path("lightning") else "none"
    if steps <= 8:
        return "lcm" if lora_path("lcm") else "none"
    return "none"


def suggested_cfg(steps: int, accel: str) -> float:
    if accel in {"lightning", "hyper"}:
        return 1.2
    if accel == "lcm":
        return 1.5
    if steps <= 8:
        return 2.5
    return 4.0


def list_checkpoints() -> list[str]:
    if CKPT_DIR.is_dir():
        names = sorted(path.name for path in CKPT_DIR.glob("*.safetensors"))
        if names:
            return names
    return [CHECKPOINTS["anima"]]


def image_options() -> dict[str, Any]:
    accels = [{"value": "none", "label": "Off"}]
    for key, label in (("lightning", "Lightning"), ("lcm", "LCM"), ("hyper", "Hyper")):
        if lora_path(key):
            accels.append({"value": key, "label": label})
    return {
        "steps": [{"value": str(n), "label": IMAGE_STEP_LABELS[n]} for n in IMAGE_STEP_CHOICES],
        "checkpoints": [
            {"value": name, "label": name.replace(".safetensors", "")} for name in list_checkpoints()
        ],
        "accel": accels,
        "default_steps": IMAGE_STEP_DEFAULT,
    }


def resolve_image_run(gen: dict[str, Any] | None) -> dict[str, Any]:
    gen = gen or {}
    steps = snap_image_steps(gen.get("image_steps") or IMAGE_STEP_DEFAULT)
    accel = (gen.get("image_accel") or "").strip().lower()
    if accel not in ACCEL:
        accel = suggested_accel(steps)
    if accel in {"lightning", "hyper"} and steps > 8:
        accel = "none"
    elif accel == "lcm" and steps > 8:
        accel = "none"
    elif accel in {"lightning", "hyper"} and steps > 4:
        steps = 4
    elif accel == "lcm":
        steps = 8
    try:
        cfg = float(gen.get("image_cfg"))
    except (TypeError, ValueError):
        cfg = suggested_cfg(steps, accel)
    else:
        if cfg <= 0:
            cfg = suggested_cfg(steps, accel)
    return {"steps": steps, "accel": accel or "none", "cfg": cfg}
