from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.ingest.classify import apply_structure, classify_text, content_type_for, heading_level_from_text
from app.ingest.models import Block, ParsedDocument
from app.ingest.ocr import capability_note, is_sparse, ocr_image_bytes


def _line_text(line: dict) -> str:
    return "".join(span.get("text", "") for span in line.get("spans") or []).strip()


def _line_size(line: dict) -> float:
    spans = line.get("spans") or []
    if not spans:
        return 0.0
    return max(float(s.get("size") or 0) for s in spans)


def _line_is_mono(line: dict) -> bool:
    for span in line.get("spans") or []:
        flags = int(span.get("flags") or 0)
        font = str(span.get("font") or "").lower()
        if flags & 8 or any(tok in font for tok in ("mono", "courier", "consolas", "menlo")):
            return True
    return False


def _heading_level(size: float, body: float, ranks: list[float]) -> int:
    if body <= 0:
        return 2
    if size >= body * 1.55:
        return 1
    if size >= body * 1.28:
        return 2
    if size >= body * 1.12:
        return 3
    # Fall back to size rank among heading-like sizes
    for i, value in enumerate(ranks[:3], start=1):
        if abs(size - value) < 0.4:
            return i
    return 2


def parse_pdf(path: Path, *, use_ocr: bool = True) -> ParsedDocument:
    import fitz

    doc = fitz.open(path)
    blocks: list[Block] = []
    warnings: list[str] = []
    native_pages = 0
    ocr_pages = 0
    empty_pages = 0
    ocr_note = capability_note() if use_ocr else "OCR disabled (--no-ocr)."

    try:
        for page_index, page in enumerate(doc, start=1):
            page_blocks, used_ocr, empty = _parse_page(
                page, page_index, use_ocr=use_ocr
            )
            blocks.extend(page_blocks)
            if empty:
                empty_pages += 1
            elif used_ocr:
                ocr_pages += 1
            else:
                native_pages += 1
            if used_ocr and ocr_note and ocr_note not in warnings:
                warnings.append(ocr_note)
    finally:
        doc.close()

    blocks = apply_structure(blocks)
    title = next((b.text for b in blocks if b.type == "heading"), path.stem)
    return ParsedDocument(
        source_path=str(path),
        source_name=path.name,
        format="pdf",
        title=title,
        page_count=native_pages + ocr_pages + empty_pages,
        native_pages=native_pages,
        ocr_pages=ocr_pages,
        empty_pages=empty_pages,
        blocks=blocks,
        warnings=warnings,
    )


def _parse_page(page, page_index: int, *, use_ocr: bool) -> tuple[list[Block], bool, bool]:
    native = _blocks_from_dict(page, page_index)
    native_text = " ".join(b.text for b in native)
    used_ocr = False

    if is_sparse(native_text) and use_ocr:
        pix = page.get_pixmap(dpi=160, alpha=False)
        ocr_text = ocr_image_bytes(pix.tobytes("png"))
        if ocr_text.strip():
            native = [
                Block(
                    type="paragraph",
                    text=ocr_text.strip(),
                    page=page_index,
                    content_type="text",
                    meta={"extraction": "ocr"},
                )
            ]
            used_ocr = True

    native.extend(_table_blocks(page, page_index))
    native.extend(_image_blocks(page, page_index))

    empty = not any(b.text.strip() for b in native)
    return native, used_ocr, empty


def _blocks_from_dict(page, page_index: int) -> list[Block]:
    data = page.get_text("dict")
    sizes: list[float] = []
    lines_out: list[tuple[str, float, bool, tuple]] = []

    for block in data.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            text = _line_text(line)
            if not text:
                continue
            size = _line_size(line)
            sizes.append(size)
            bbox = tuple(line.get("bbox") or (0, 0, 0, 0))
            lines_out.append((text, size, _line_is_mono(line), bbox))

    if not lines_out:
        return []

    sizes_sorted = sorted(sizes)
    body = sizes_sorted[len(sizes_sorted) // 2]
    heading_sizes = sorted({round(s, 1) for s in sizes if s >= body * 1.12}, reverse=True)

    blocks: list[Block] = []
    buf: list[str] = []
    buf_kind = "paragraph"
    buf_level: int | None = None

    def flush() -> None:
        nonlocal buf, buf_kind, buf_level
        if not buf:
            return
        text = "\n".join(buf).strip()
        block_type = buf_kind  # type: ignore[assignment]
        blocks.append(
            Block(
                type=block_type,
                text=text,
                page=page_index,
                level=buf_level,
                content_type=content_type_for(block_type),
                meta={"extraction": "native"},
            )
        )
        buf = []
        buf_kind = "paragraph"
        buf_level = None

    for text, size, mono, _bbox in lines_out:
        is_heading = (
            size >= body * 1.15
            and len(text) < 140
            and not text.endswith((".", ",", ";", ":"))
        ) or (size >= body * 1.4 and len(text) < 200)

        if mono and not is_heading:
            kind = "code"
            level = None
        elif is_heading:
            kind = "heading"
            level = heading_level_from_text(
                text, default=_heading_level(size, body, heading_sizes)
            )
        else:
            kind = "list_item" if text[:2] in {"- ", "* ", "• "} or (
                text[:3].rstrip(".").isdigit() and "." in text[:4]
            ) else "paragraph"
            level = None

        cue = classify_text(text) if kind == "paragraph" else None
        if cue:
            flush()
            buf_kind = cue
            buf_level = None
            buf = [text]
            flush()
            continue

        if kind != buf_kind or kind == "heading":
            flush()
            buf_kind = kind
            buf_level = level
            buf = [text]
            if kind == "heading":
                flush()
            continue

        buf.append(text)

    flush()
    return blocks


def _table_blocks(page, page_index: int) -> list[Block]:
    try:
        finder = page.find_tables()
        tables = finder.tables if finder else []
    except Exception:
        return []
    out: list[Block] = []
    for table in tables:
        try:
            rows = table.extract()
        except Exception:
            continue
        if not rows:
            continue
        lines = []
        for row in rows:
            cells = [str(c).strip() if c is not None else "" for c in row]
            if any(cells):
                lines.append(" | ".join(cells))
        if lines:
            out.append(
                Block(
                    type="table",
                    text="\n".join(lines),
                    page=page_index,
                    content_type="table",
                    meta={"extraction": "native", "rows": len(lines)},
                )
            )
    return out


def _image_blocks(page, page_index: int) -> list[Block]:
    out: list[Block] = []
    try:
        images = page.get_images(full=True)
    except Exception:
        return out
    if not images:
        return out
    out.append(
        Block(
            type="figure",
            text=f"[{len(images)} figure(s) on page {page_index}]",
            page=page_index,
            content_type="figure",
            meta={"extraction": "native", "count": len(images)},
        )
    )
    return out
