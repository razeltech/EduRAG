from __future__ import annotations

import re
from pathlib import Path

from app.ingest.classify import apply_structure, content_type_for
from app.ingest.models import Block, ParsedDocument

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^```")
_TABLE_ROW = re.compile(r"^\|.+\|$")
_LIST = re.compile(r"^(\s*)([-*+]|(\d+[.)]))\s+")


def parse_markdown(path: Path, *, use_ocr: bool = True) -> ParsedDocument:
    del use_ocr
    raw = path.read_text(encoding="utf-8", errors="ignore")
    blocks: list[Block] = []
    para: list[str] = []
    in_code = False
    code: list[str] = []
    table: list[str] = []

    def flush_para() -> None:
        if not para:
            return
        text = "\n".join(para).strip()
        if text:
            blocks.append(
                Block(type="paragraph", text=text, content_type=content_type_for("paragraph"))
            )
        para.clear()

    def flush_table() -> None:
        if not table:
            return
        rows = [row for row in table if not re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", row)]
        if rows:
            cleaned = [" | ".join(c.strip() for c in r.strip("|").split("|")) for r in rows]
            blocks.append(Block(type="table", text="\n".join(cleaned), content_type="table"))
        table.clear()

    for line in raw.splitlines():
        if _FENCE.match(line.strip()):
            if in_code:
                blocks.append(
                    Block(type="code", text="\n".join(code).rstrip(), content_type="code")
                )
                code = []
                in_code = False
            else:
                flush_para()
                flush_table()
                in_code = True
            continue
        if in_code:
            code.append(line)
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_para()
            flush_table()
            blocks.append(
                Block(
                    type="heading",
                    text=heading.group(2).strip(),
                    level=len(heading.group(1)),
                    content_type="text",
                )
            )
            continue

        if _TABLE_ROW.match(line.strip()):
            flush_para()
            table.append(line.strip())
            continue
        else:
            flush_table()

        if _LIST.match(line):
            flush_para()
            item = _LIST.sub("", line).strip()
            if item:
                blocks.append(
                    Block(type="list_item", text=item, content_type="text")
                )
            continue

        if not line.strip():
            flush_para()
            continue
        para.append(line.rstrip())

    flush_para()
    flush_table()
    if in_code and code:
        blocks.append(Block(type="code", text="\n".join(code).rstrip(), content_type="code"))

    blocks = apply_structure(blocks)
    title = next((b.text for b in blocks if b.type == "heading"), path.stem)
    return ParsedDocument(
        source_path=str(path),
        source_name=path.name,
        format="md",
        title=title,
        page_count=1,
        native_pages=1 if blocks else 0,
        empty_pages=0 if blocks else 1,
        blocks=blocks,
    )
