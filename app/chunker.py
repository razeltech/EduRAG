"""Turn parsed blocks into teachable units — one concept, example, or definition."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.ingest.models import Block, ParsedDocument

MAX_CHARS = 1400
MIN_CHARS = 120


@dataclass
class Chunk:
    text: str
    chunk_index: int
    chapter: str | None = None
    section: str | None = None
    page: int | None = None
    source_file: str = ""
    content_type: str = "text"
    heading_path: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ATOMIC = {"table", "code", "example", "definition", "qa", "figure"}


def _path(chapter: str | None, section: str | None) -> str:
    parts = [p for p in (chapter, section) if p]
    return " > ".join(parts)


def _flush(parts: list[Block], source: str, index: int) -> Chunk | None:
    if not parts:
        return None
    texts = [b.text.strip() for b in parts if b.text.strip()]
    if not texts:
        return None
    text = "\n\n".join(texts)
    types = [b.content_type for b in parts]
    atomic = [t for t in types if t in _ATOMIC]
    content_type = atomic[0] if len(set(atomic)) == 1 else (
        atomic[0] if atomic else "text"
    )
    first = parts[0]
    return Chunk(
        text=text,
        chunk_index=index,
        chapter=first.chapter,
        section=first.section,
        page=first.page,
        source_file=source,
        content_type=content_type,
        heading_path=_path(first.chapter, first.section),
        meta={"block_types": [b.type for b in parts]},
    )


def chunk_document(doc: ParsedDocument) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[Block] = []
    buf_chars = 0
    source = doc.source_name

    def push() -> None:
        nonlocal buf, buf_chars
        chunk = _flush(buf, source, len(chunks))
        if chunk:
            chunks.append(chunk)
        buf = []
        buf_chars = 0

    for block in doc.blocks:
        text = block.text.strip()
        if not text:
            continue

        if block.type == "heading":
            if buf:
                push()
            continue

        piece = len(text)
        atomic = block.content_type in _ATOMIC or block.type in _ATOMIC

        if atomic:
            if buf_chars and buf_chars + piece > MAX_CHARS:
                push()
            buf.append(block)
            buf_chars += piece
            if buf_chars >= MIN_CHARS:
                push()
            continue

        if buf_chars + piece > MAX_CHARS and buf:
            push()
        buf.append(block)
        buf_chars += piece
        if buf_chars >= MAX_CHARS:
            push()

    if buf:
        push()

    # Merge a tiny trailing chunk into the previous one when they share a section.
    if len(chunks) >= 2 and len(chunks[-1].text) < MIN_CHARS:
        prev, last = chunks[-2], chunks[-1]
        if prev.section == last.section and prev.chapter == last.chapter:
            prev.text = prev.text + "\n\n" + last.text
            chunks.pop()

    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i
    return chunks


def format_chunks(doc: ParsedDocument, chunks: list[Chunk]) -> str:
    lines = [
        "CHUNKS",
        "======",
        f"File:    {doc.source_name}",
        f"Title:   {doc.title}",
        f"Blocks:  {len(doc.blocks)} → chunks: {len(chunks)}",
        "",
    ]
    for chunk in chunks:
        head = chunk.heading_path or "(no heading)"
        page = f" p.{chunk.page}" if chunk.page else ""
        preview = chunk.text.replace("\n", " / ")
        if len(preview) > 180:
            preview = preview[:177] + "..."
        lines.append(
            f"[{chunk.chunk_index}] {chunk.content_type} | {head}{page} | {len(chunk.text)} chars"
        )
        lines.append(f"    {preview}")
        lines.append("")
    return "\n".join(lines)
