from __future__ import annotations

from pathlib import Path

from app.ingest.classify import apply_structure, content_type_for
from app.ingest.models import Block, ParsedDocument


def parse_text(path: Path, *, use_ocr: bool = True) -> ParsedDocument:
    del use_ocr
    raw = path.read_text(encoding="utf-8", errors="ignore")
    blocks: list[Block] = []
    for chunk in raw.split("\n\n"):
        text = chunk.strip()
        if not text:
            continue
        lines = text.splitlines()
        if len(lines) == 1 and len(text) < 80 and not text.endswith("."):
            blocks.append(
                Block(type="heading", text=text, level=2, content_type="text")
            )
        else:
            blocks.append(
                Block(
                    type="paragraph",
                    text=text,
                    content_type=content_type_for("paragraph"),
                )
            )
    blocks = apply_structure(blocks)
    title = next((b.text for b in blocks if b.type == "heading"), path.stem)
    return ParsedDocument(
        source_path=str(path),
        source_name=path.name,
        format="txt",
        title=title,
        page_count=1,
        native_pages=1 if blocks else 0,
        empty_pages=0 if blocks else 1,
        blocks=blocks,
    )
