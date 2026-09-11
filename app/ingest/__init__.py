"""Phase 1 — scan files, parse structure, OCR only when native text is missing."""

from app.ingest.models import Block, ParsedDocument
from app.ingest.service import ingest_path

__all__ = ["Block", "ParsedDocument", "ingest_path"]
