"""Label blocks as example / definition / Q&A from textbook-style cues."""
from __future__ import annotations

import re

from app.ingest.models import Block, BlockType, ContentType

_EXAMPLE = re.compile(
    r"^(worked\s+)?examples?\s*(\d+|[A-Z])?\s*[:.)\-–]?",
    re.IGNORECASE,
)
_DEFINITION = re.compile(
    r"^(definition|theorem|lemma|corollary|postulate|law|principle|formula)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"^(q(?:uestion)?|exercise|problem)\s*[\d.)\:]|^q\s*\d+",
    re.IGNORECASE,
)
_ANSWER = re.compile(r"^(a(?:nswer)?|sol(?:ution)?)\s*[:.)\-–]", re.IGNORECASE)
_CHAPTER = re.compile(r"^(chapter|unit|module)\s+[\dIVXLC]+", re.IGNORECASE)
_FIGURE = re.compile(r"^(fig(?:ure)?|table|diagram)\s*[\d.]+", re.IGNORECASE)

_TYPE_TO_CONTENT: dict[BlockType, ContentType] = {
    "heading": "text",
    "paragraph": "text",
    "list_item": "text",
    "table": "table",
    "code": "code",
    "figure": "figure",
    "example": "example",
    "definition": "definition",
    "qa": "qa",
}


def content_type_for(block_type: BlockType) -> ContentType:
    return _TYPE_TO_CONTENT.get(block_type, "text")


def heading_level_from_text(text: str, default: int = 2) -> int:
    if _CHAPTER.match(text.strip()):
        return 1
    return default


def classify_text(text: str) -> BlockType | None:
    stripped = text.strip()
    if not stripped:
        return None
    if _EXAMPLE.match(stripped):
        return "example"
    if _DEFINITION.match(stripped):
        return "definition"
    if _QUESTION.match(stripped) or _ANSWER.match(stripped):
        return "qa"
    if _FIGURE.match(stripped) and len(stripped) < 180:
        return "figure"
    return None


def apply_structure(blocks: list[Block]) -> list[Block]:
    """Fill chapter/section from headings and relabel textbook patterns."""
    chapter: str | None = None
    section: str | None = None
    out: list[Block] = []
    pending_q: Block | None = None

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        if block.type == "heading":
            if (block.level or 2) <= 1 or _CHAPTER.match(text):
                chapter = text
                section = None
                if block.level is None:
                    block.level = 1
            else:
                section = text
            block.chapter = chapter
            block.section = section
            block.content_type = "text"
            out.append(block)
            pending_q = None
            continue

        guessed = classify_text(text)
        if guessed and block.type in {"paragraph", "list_item"}:
            block.type = guessed
            block.content_type = content_type_for(guessed)

        if block.type == "qa" and _QUESTION.match(text):
            pending_q = block
        elif pending_q is not None and block.type in {"paragraph", "qa"} and _ANSWER.match(text):
            pending_q.text = pending_q.text.rstrip() + "\n\n" + text
            pending_q.type = "qa"
            pending_q.content_type = "qa"
            pending_q = None
            continue
        else:
            pending_q = None

        block.chapter = chapter
        block.section = section
        if not block.content_type:
            block.content_type = content_type_for(block.type)
        out.append(block)

    return out
