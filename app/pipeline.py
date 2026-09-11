"""Parse → chunk → embed → SQLite index."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.chunker import chunk_document
from app.db import default_institution_id, init_db
from app.db.store import Store
from app.embed import get_embedder
from app.ingest.service import ingest_path


def index_path(
    path: Path,
    course_name: str,
    *,
    use_ocr: bool = True,
    institution_id: str | None = None,
    include_images: bool | None = None,
    max_files: int | None = None,
) -> dict[str, Any]:
    conn = init_db()
    store = Store(conn)
    iid = institution_id or default_institution_id(conn)
    course = store.get_or_create_course(course_name, iid)
    embedder = get_embedder()
    folder = path.is_dir()
    parsed = ingest_path(
        path,
        use_ocr=use_ocr and not folder,
        include_images=include_images if include_images is not None else not folder,
        max_files=max_files,
    )
    results = []
    for doc in parsed:
        chunks = chunk_document(doc)
        if not chunks:
            results.append(
                {
                    "filename": doc.source_name,
                    "chunk_count": 0,
                    "warning": "No chunks produced",
                }
            )
            continue
        vectors = embedder.encode([c.text for c in chunks])
        saved = store.add_document(
            course=course,
            filename=doc.source_name,
            source_path=doc.source_path,
            fmt=doc.format,
            page_count=doc.page_count,
            chunks=[c.to_dict() for c in chunks],
            vectors=vectors,
        )
        results.append(saved)
    return {
        "course": {"id": course["id"], "name": course["name"]},
        "documents": results,
    }
