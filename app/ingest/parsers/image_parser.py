from __future__ import annotations

from pathlib import Path

from app.ingest.classify import apply_structure
from app.ingest.models import Block, ParsedDocument
from app.ingest.ocr import capability_note, ocr_image_path


def parse_image(path: Path, *, use_ocr: bool = True) -> ParsedDocument:
    warnings: list[str] = []
    text = ""
    if use_ocr:
        note = capability_note()
        if note:
            warnings.append(note)
        text = ocr_image_path(path).strip()
        if not text and not warnings:
            warnings.append("OCR returned no text.")
    else:
        warnings.append("OCR disabled (--no-ocr); image skipped.")

    blocks: list[Block] = []
    if text:
        blocks.append(
            Block(
                type="paragraph",
                text=text,
                page=1,
                content_type="text",
                meta={"extraction": "ocr"},
            )
        )
    blocks = apply_structure(blocks)
    empty = 0 if blocks else 1
    return ParsedDocument(
        source_path=str(path),
        source_name=path.name,
        format=path.suffix.lower().lstrip("."),
        title=path.stem,
        page_count=1,
        native_pages=0,
        ocr_pages=1 if blocks else 0,
        empty_pages=empty,
        blocks=blocks,
        warnings=warnings,
    )
