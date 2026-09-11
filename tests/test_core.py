from pathlib import Path

from app.chunker import chunk_document
from app.ingest.parsers import parse_file
from app.rag import extract_quiz, validate_citations
from app.safety import detect_distress

FIXTURES = Path(__file__).parent / "fixtures"


def test_chunker_keeps_teachable_units():
    doc = parse_file(FIXTURES / "sample_chapter.md", use_ocr=False)
    chunks = chunk_document(doc)
    assert len(chunks) >= 3
    types = {c.content_type for c in chunks}
    assert "example" in types or "definition" in types
    assert any("uniform" in c.text.lower() or "Motion" in (c.chapter or "") for c in chunks)


def test_citation_validation_drops_fakes():
    cleaned, used = validate_citations("Velocity is constant [1] but also [99] and [2].", 2)
    assert used == [1, 2]
    assert "[99]" not in cleaned
    assert "[1]" in cleaned


def test_citation_cleanup_keeps_code_indent():
    src = "Claim [1].\n\n```csharp\nvoid Start() {\n    int x = 1;\n    if (true) {\n        return;\n    }\n}\n```\n"
    cleaned, used = validate_citations(src, 1)
    assert used == [1]
    assert "    int x = 1;" in cleaned
    assert "        return;" in cleaned


def test_quiz_extract():
    text, quiz = extract_quiz('Hello\n```quiz\n{"question": "SI unit?", "answer": "m/s"}\n```\n')
    assert "SI unit?" in (quiz or {}).get("question", "")
    assert "```" not in text


def test_open_chat_does_not_require_library():
    from app.personas import DEFAULT_PERSONA_ID
    from app.rag import build_messages

    assert DEFAULT_PERSONA_ID == "chat"
    messages = build_messages(
        persona_id="chat",
        question="hey, long day",
        history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey — what's up?"}],
        context="",
        has_passages=False,
    )
    assert messages[-1]["content"] == "hey, long day"
    assert "ONLY the" not in messages[0]["content"]
    assert "Local clock:" in messages[0]["content"]


def test_tutor_with_passages_stays_grounded():
    from app.rag import build_messages

    messages = build_messages(
        persona_id="tutor",
        question="what is velocity",
        history=[],
        context="[1] notes.md | Motion\nVelocity is speed with direction.",
        has_passages=True,
    )
    assert "Context passages:" in messages[-1]["content"]
    assert "ONLY the" in messages[0]["content"]


def test_distress_detection():
    assert detect_distress("I want to kill myself")
    assert detect_distress("normal homework question") is None


def test_code_queries_prefer_code_chunks():
    from app.retrieve import heading_boost, prefers_code

    assert prefers_code("how do I move a Transform in csharp")
    assert not prefers_code("what is photosynthesis")
    chunks = [
        {
            "heading_path": "Manual/Transform",
            "chapter": "Transform",
            "section": "",
            "source_file": "Transform.html",
            "text": "x",
        },
        {
            "heading_path": "Lighting",
            "chapter": "Light",
            "section": "",
            "source_file": "Light.html",
            "text": "y",
        },
    ]
    hits = heading_boost("transform translate", chunks)
    assert hits and hits[0][0] == 0


def test_smalltalk_skips_retrieval():
    from types import SimpleNamespace
    from app.rag import should_retrieve

    chat = SimpleNamespace(uses_library=False)
    docs = SimpleNamespace(uses_library=True)
    assert not should_retrieve(chat, "yeah i didnt eat today", "course1")
    assert should_retrieve(chat, "how do I use Transform.Translate", "course1")
    assert should_retrieve(docs, "yeah i didnt eat today", "course1")
    assert not should_retrieve(chat, "hi", "course1")


def test_lexical_rerank_prefers_query_overlap():
    from app.rerank import lexical_rerank

    chunks = [
        {"text": "chlorophyll and photosynthesis in leaves", "content_type": "text"},
        {"text": "Transform.Translate moves a Unity object in C#", "content_type": "code"},
    ]
    fused = [(0, 0.55), (1, 0.50)]
    ranked = lexical_rerank("unity transform translate csharp", chunks, fused, top_k=2)
    assert ranked[0][0] == 1
    assert ranked[0][1] > ranked[1][1]


def test_k12_prompt_is_conservative():
    from app.rag import build_messages

    messages = build_messages(
        persona_id="chat",
        question="hey",
        history=[],
        context="",
        has_passages=False,
        age_band="k12",
    )
    assert "K-12" in messages[0]["content"]
    adult = build_messages(
        persona_id="chat",
        question="hey",
        history=[],
        context="",
        has_passages=False,
        age_band="adult",
    )
    assert "K-12" not in adult[0]["content"]


def test_teen_safeguard_on_normal_chat():
    from app.rag import build_messages

    messages = build_messages(
        persona_id="chat",
        question="hey",
        history=[],
        context="",
        has_passages=False,
    )
    assert "16+" in messages[0]["content"]
    assert "erotic" in messages[0]["content"].lower()


def test_k12_overrides_would_be_adult_tone():
    from app.rag import build_messages

    messages = build_messages(
        persona_id="chat",
        question="hey",
        history=[],
        context="",
        has_passages=False,
        age_band="k12",
    )
    assert "K-12" in messages[0]["content"]
    assert "16+" in messages[0]["content"]


def test_school_characters_reject_adult(tmp_path, monkeypatch):
    from app import characters as ch

    monkeypatch.setattr(ch, "CHAR_PATH", tmp_path / "characters.json")
    owner = {"id": "u1", "role": "admin"}
    try:
        ch.upsert(
            {
                "name": "Home",
                "system_prompt": "You are my girlfriend. We are adults.",
                "private": True,
                "rating": "adult",
                "adult_confirm": True,
                "filters": {"adult_private": True},
            },
            as_new=True,
            owner=owner,
        )
        assert False, "adult save should be rejected"
    except ValueError as exc:
        assert "private room" in str(exc).lower() or "companion" in str(exc).lower()


def test_leftover_adult_hidden_from_school_list(tmp_path, monkeypatch):
    from app import characters as ch

    monkeypatch.setattr(ch, "CHAR_PATH", tmp_path / "characters.json")
    ch.CHAR_PATH.write_text(
        '[{"id":"c_secret","name":"Home","system_prompt":"hi","rating":"adult","private":true,"owner_user_id":"u1"}]',
        encoding="utf-8",
    )
    owner = {"id": "u1", "role": "admin"}
    ids = {p.id for p in ch.list_merged(owner)}
    assert "c_secret" not in ids
    assert ch.resolve("c_secret", owner).id == "chat"
    assert ch.editor_payload("c_secret", owner) is None


def test_companion_unlock_and_adult_persona(tmp_path, monkeypatch):
    import sqlite3

    from app import companion as room
    from app.auth import verify_password
    from app.db import init_db
    from app.db.store import Store
    from app.rag import build_messages

    monkeypatch.setattr(room, "STATE_PATH", tmp_path / "companion.json")
    monkeypatch.setattr(room, "KEY_PATH", tmp_path / "companion.key")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store = Store(init_db(conn))
    room.ensure_ready(store)
    key = room.KEY_PATH.read_text(encoding="utf-8").strip()
    assert key == room.DEFAULT_KEY
    assert verify_password(key, room.load_state()["unlock_hash"])
    try:
        room.unlock("nope", store)
        assert False, "bad key should fail"
    except ValueError:
        pass
    out = room.unlock(key, store, adult_confirm=True)
    assert out["token"]
    assert out["profile"]["adult_confirm"] is True
    persona = room.persona()
    assert persona.rating == "adult"
    assert persona.private is True
    assert persona.id == room.PERSONA_ID
    assert persona.name == "Maya"
    assert "Your name is Maya" in persona.system_prompt
    messages = build_messages(
        persona_id=persona.id,
        question="hey",
        history=[],
        context="",
        has_passages=False,
        persona=persona,
    )
    assert "18+" in messages[0]["content"] or "adult" in messages[0]["content"].lower()
    assert "helpdesk" in messages[0]["content"].lower()
    assert "girlfriend" in persona.system_prompt.lower()
    assert "chatbot" not in persona.system_prompt.lower()

    room.update_profile(
        {
            "name": "Maya",
            "partner_role": "girlfriend",
            "system_prompt": persona.system_prompt,
            "adult_confirm": True,
            "user_name": "Arjun",
            "user_gender": "man",
            "user_pronouns": "he/him",
            "user_called": "love",
            "user_about": "quiet, works nights",
        }
    )
    p2 = room.persona()
    assert "Arjun" in p2.system_prompt
    assert "he/him" in p2.system_prompt
    assert "love" in p2.system_prompt
    assert room.public_profile()["needs_you"] is False


def test_needs_continue_detects_cut_code():
    from app.rag import needs_continue

    assert needs_continue('```csharp\nvoid Update() {\nDebug.Log("Player " + board[new')
    assert needs_continue("if (board[new Vector2Int(i, 0)] == board[new Vector2Int(")
    assert not needs_continue("```csharp\nint x = 1;\n```")
    assert not needs_continue("All good. That's the move.")
