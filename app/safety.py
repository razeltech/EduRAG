"""Distress / crisis routing — runs for every persona, not only Guide."""
from __future__ import annotations

import re

# Phrases, not a diagnostic tool. False positives are acceptable; misses are not.
_PATTERNS = [
    r"\bkill myself\b",
    r"\bsuicid",
    r"\bself[-\s]?harm\b",
    r"\bwant to die\b",
    r"\bend my life\b",
    r"\bcut myself\b",
    r"\bhurt myself\b",
    r"\bno reason to live\b",
    r"\bbetter off dead\b",
    r"\bcan't go on\b",
    r"\bcannot go on\b",
    r"\bbeing abused\b",
    r"\bsexually abused\b",
    r"\brap(?:e|ed|ing)\b",
    r"\bbeing beaten\b",
    r"\bmy parents hit me\b",
    r"\bi'm going to hurt\b",
    r"\bgoing to kill\b",
]

_RE = re.compile("|".join(_PATTERNS), re.IGNORECASE)

ESCALATION_REPLY = (
    "Thank you for telling me. I'm not a counselor or a doctor, and I should "
    "not try to handle this myself. A real teacher or counselor needs to know "
    "— I've raised a flag for staff on this conversation.\n\n"
    "If you are in immediate danger, contact local emergency services now.\n\n"
    "I can stay with you on a school question if you want, or we can stop here."
)


def detect_distress(text: str) -> str | None:
    if not text:
        return None
    match = _RE.search(text)
    if not match:
        return None
    return match.group(0)
