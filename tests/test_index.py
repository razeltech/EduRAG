from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_index_and_hybrid_search(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("EDURAG_DB", str(db))
    from app.pipeline import index_path
    from app.db import init_db
    from app.db.store import Store
    from app.rag import retrieve_for_course

    result = index_path(FIXTURES / "sample_chapter.md", "Grade 10 Physics", use_ocr=False)
    assert result["documents"][0]["chunk_count"] > 0
    store = Store(init_db())
    course = store.get_or_create_course("Grade 10 Physics")
    debug = retrieve_for_course(course["id"], "What is uniform motion?", store, top_k=3)
    assert debug["final"]
    blob = " ".join(c["text"].lower() for c in debug["final"])
    assert "uniform" in blob or "velocity" in blob
