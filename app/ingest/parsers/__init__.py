from __future__ import annotations

from pathlib import Path

from app.ingest.models import ParsedDocument
from app.ingest.parsers.docx_parser import parse_docx
from app.ingest.parsers.html_parser import parse_html
from app.ingest.parsers.image_parser import parse_image
from app.ingest.parsers.markdown_parser import parse_markdown
from app.ingest.parsers.pdf_parser import parse_pdf
from app.ingest.parsers.pptx_parser import parse_pptx
from app.ingest.parsers.text_parser import parse_text

_DISPATCH = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".pptx": parse_pptx,
    ".html": parse_html,
    ".htm": parse_html,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".txt": parse_text,
    ".png": parse_image,
    ".jpg": parse_image,
    ".jpeg": parse_image,
    ".webp": parse_image,
    ".tif": parse_image,
    ".tiff": parse_image,
}


def supported_extensions() -> list[str]:
    return sorted(_DISPATCH)


def parse_file(path: Path, *, use_ocr: bool = True) -> ParsedDocument:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    ext = path.suffix.lower()
    parser = _DISPATCH.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported file type '{ext}'")
    return parser(path, use_ocr=use_ocr)
