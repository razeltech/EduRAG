from __future__ import annotations

from app.ingest.models import ParsedDocument


def format_document(doc: ParsedDocument, *, preview_blocks: int = 8) -> str:
    counts = doc.block_counts()
    count_str = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "none"
    lines = [
        "INGEST",
        "======",
        f"File:     {doc.source_name}",
        f"Path:     {doc.source_path}",
        f"Format:   {doc.format}",
        f"Title:    {doc.title or '(none)'}",
        f"Pages:    {doc.page_count}  "
        f"(native: {doc.native_pages}, OCR: {doc.ocr_pages}, empty: {doc.empty_pages})",
        f"Blocks:   {len(doc.blocks)}  ({count_str})",
        f"Chars:    {len(doc.text)}",
    ]
    if doc.warnings:
        lines.append("Warnings:")
        for warning in doc.warnings:
            lines.append(f"  - {warning}")

    outline = doc.outline()
    if outline:
        lines.append("")
        lines.append("Outline:")
        for heading in outline[:40]:
            indent = "  " * max((heading.level or 1) - 1, 0)
            page = f"  p.{heading.page}" if heading.page else ""
            lines.append(f"  {indent}H{heading.level or '?'} {heading.text}{page}")
        if len(outline) > 40:
            lines.append(f"  ... {len(outline) - 40} more headings")

    if doc.blocks:
        lines.append("")
        lines.append(f"Preview (first {min(preview_blocks, len(doc.blocks))} blocks):")
        for block in doc.blocks[:preview_blocks]:
            page = f"p.{block.page} " if block.page else ""
            snippet = block.text.replace("\n", " / ")
            if len(snippet) > 140:
                snippet = snippet[:137] + "..."
            extra = f" [{block.chapter}]" if block.chapter else ""
            lines.append(f"  - {page}{block.type}/{block.content_type}{extra}: {snippet}")
    return "\n".join(lines)


def format_batch(docs: list[ParsedDocument]) -> str:
    if len(docs) == 1:
        return format_document(docs[0])
    lines = [
        "INGEST BATCH",
        "============",
        f"Files: {len(docs)}",
        "",
    ]
    for doc in docs:
        counts = doc.block_counts()
        warn = f"  warnings={len(doc.warnings)}" if doc.warnings else ""
        lines.append(
            f"- {doc.source_name}  [{doc.format}]  "
            f"pages={doc.page_count} native={doc.native_pages} ocr={doc.ocr_pages} "
            f"blocks={len(doc.blocks)} chars={len(doc.text)}{warn}"
        )
        if counts:
            lines.append("    " + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
    lines.append("")
    lines.append("First file detail:")
    lines.append("")
    lines.append(format_document(docs[0]))
    return "\n".join(lines)
