from __future__ import annotations

from pathlib import Path

from app.ingest.models import ParsedDocument
from app.ingest.parsers import parse_file
from app.ingest.scanner import scan


def ingest_path(
    path: Path,
    *,
    use_ocr: bool = True,
    include_images: bool = True,
    max_files: int | None = None,
) -> list[ParsedDocument]:
    files = scan(path, include_images=include_images, max_files=max_files)
    docs: list[ParsedDocument] = []
    for file in files:
        docs.append(parse_file(file, use_ocr=use_ocr))
    return docs
