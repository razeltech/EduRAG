"""Grounded generate: retrieve → prompt → stream → validate citations."""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from app.embed import get_embedder
from app.llm import chat_stream
from app.personas import (
    ADULT_PRIVATE,
    COMPANION_CONVERSE,
    CONVERSE,
    GROUNDING,
    TEEN_SAFE,
    get_persona,
)
from app.retrieve import hybrid_search, prefers_code
from app.safety import ESCALATION_REPLY, detect_distress

CITE_RE = re.compile(r"\[(\d+)\]")
QUIZ_RE = re.compile(r"```quiz\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
KNOWLEDGE_TURN = re.compile(
    r"\b(how do i|how to|what is|where is|unity|unreal|api|error|script|docs|"
    r"manual|code|compile|shader|transform|prefab|c#|csharp|why does|explain)\b",
    re.I,
)


def clock_line() -> str:
    now = datetime.now()
    stamp = now.strftime("%A, %B %d, %Y, %I:%M %p")
    stamp = stamp.replace(" 0", " ").replace(", 0", ", ")
    hour = now.hour
    if 5 <= hour < 11:
        period = "morning"
    elif 11 <= hour < 16:
        period = "afternoon"
    elif 16 <= hour < 21:
        period = "evening"
    else:
        period = "night"
    return (
        f"Local clock: {stamp} ({period}). "
        "Match this hour. Do not suggest lunch at night, breakfast in the evening, "
        "or 'good morning' after noon."
    )


def should_retrieve(persona: Any, question: str, course_id: str | None) -> bool:
    if not course_id:
        return False
    if getattr(persona, "uses_library", True):
        return True
    q = (question or "").strip()
    if len(q) < 8:
        return False
    return bool(KNOWLEDGE_TURN.search(q)) or prefers_code(q)


def validate_citations(answer: str, n: int) -> tuple[str, list[int]]:
    used: list[int] = []

    def repl(match: re.Match[str]) -> str:
        num = int(match.group(1))
        if 1 <= num <= n:
            if num not in used:
                used.append(num)
            return match.group(0)
        return ""

    cleaned = CITE_RE.sub(repl, answer)
    cleaned = _collapse_prose_spaces(cleaned)
    return cleaned.strip(), used


def _collapse_prose_spaces(text: str) -> str:
    """Squeeze spaces in prose only — never inside fenced code."""
    out: list[str] = []
    i = 0
    while i < len(text):
        start = text.find("```", i)
        if start < 0:
            out.append(re.sub(r"[^\S\n]+", " ", text[i:]))
            break
        out.append(re.sub(r"[^\S\n]+", " ", text[i:start]))
        end = text.find("```", start + 3)
        if end < 0:
            out.append(text[start:])
            break
        out.append(text[start : end + 3])
        i = end + 3
    return "".join(out)


def extract_quiz(answer: str) -> tuple[str, dict[str, Any] | None]:
    match = QUIZ_RE.search(answer)
    if not match:
        return answer, None
    quiz = None
    try:
        quiz = json.loads(match.group(1))
        if not isinstance(quiz, dict) or "question" not in quiz:
            quiz = None
    except json.JSONDecodeError:
        quiz = None
    cleaned = QUIZ_RE.sub("", answer).strip()
    return cleaned, quiz


def build_context(chunks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    if not chunks:
        return (
            "(No course passages were retrieved for this question. There is nothing to cite.)",
            [],
        )
    lines = []
    citations = []
    for i, chunk in enumerate(chunks, start=1):
        src = chunk.get("source_file") or "document"
        loc = chunk.get("heading_path") or ""
        page = f" p.{chunk['page']}" if chunk.get("page") else ""
        header = f"[{i}] {src} | {loc}{page}".strip(" |")
        body = chunk.get("text") or ""
        if len(body) > 900:
            body = body[:900].rsplit(" ", 1)[0] + "…"
        lines.append(header + "\n" + body)
        citations.append(
            {
                "n": i,
                "source_file": src,
                "chapter": chunk.get("chapter"),
                "section": chunk.get("section"),
                "page": chunk.get("page"),
                "content_type": chunk.get("content_type"),
                "snippet": chunk["text"][:280],
                "heading_path": loc,
            }
        )
    return "\n\n".join(lines), citations


def build_messages(
    *,
    persona_id: str,
    question: str,
    history: list[dict[str, str]],
    context: str,
    weak_topics: list[str] | None = None,
    has_passages: bool = False,
    age_band: str = "adult",
    persona: Any | None = None,
) -> list[dict[str, str]]:
    persona = persona or get_persona(persona_id)
    now = clock_line()
    weak = ""
    if weak_topics:
        weak = "Weak topics for this student: " + ", ".join(weak_topics[:6]) + "."
    k12 = ""
    rating = getattr(persona, "rating", "teen") or "teen"
    if age_band == "k12":
        rating = "teen"
        k12 = (
            "This library is flagged K-12. Conservative tone. No adult, romantic, "
            "or violent roleplay. Keep language school-appropriate."
        )
    band = ADULT_PRIVATE if rating == "adult" else TEEN_SAFE
    grounded = persona.uses_library and has_passages
    if grounded:
        system = "\n\n".join(
            p for p in (GROUNDING, TEEN_SAFE, persona.system_prompt, weak, k12, now) if p
        )
        user_content = f"Context passages:\n{context}\n\nUser:\n{question}"
    else:
        extra = ""
        if has_passages:
            extra = (
                "Optional library passages — use only if this message is about them; "
                "cite [n]. Ignore them for small talk:\n"
                + context
            )
        converse = COMPANION_CONVERSE if rating == "adult" else CONVERSE
        system = "\n\n".join(
            p
            for p in (band, persona.system_prompt, converse, extra, weak, k12, now)
            if p
        )
        user_content = question
    messages = [{"role": "system", "content": system}]
    cap = 28 if rating == "adult" else 16
    keep = max(4, min(persona.history_turns, cap))
    for item in history[-keep:]:
        if item.get("role") not in {"user", "assistant"} or not item.get("content"):
            continue
        content = item["content"]
        if item["role"] == "assistant" and len(content) > 1600:
            content = content[:1200] + "\n…[earlier reply trimmed]…"
        messages.append({"role": item["role"], "content": content})
    messages.append({"role": "user", "content": user_content})
    return messages


def retrieve_for_course(
    course_id: str,
    question: str,
    store,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    chunks, matrix = store.load_index(course_id)
    embedder = get_embedder()
    qvec = embedder.encode_query(question)
    return hybrid_search(question, qvec, chunks, matrix, candidate_k=16, top_k=top_k)


def generate_answer(
    *,
    question: str,
    persona_id: str,
    course_id: str | None,
    history: list[dict[str, str]],
    store,
    user_id: str | None = None,
    conversation_id: str | None = None,
    viewer: dict[str, Any] | None = None,
    persona_obj: Any | None = None,
    num_predict: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield dict events: meta, token, done, escalation."""
    distress = detect_distress(question)
    if distress and user_id:
        store.add_escalation(
            user_id, conversation_id, f"distress:{distress}", question
        )
        yield {"event": "escalation", "reason": distress}
        yield {"event": "token", "text": ESCALATION_REPLY}
        yield {
            "event": "done",
            "answer": ESCALATION_REPLY,
            "citations": [],
            "quiz": None,
            "debug": {"distress": True, "reason": distress},
        }
        return

    debug: dict[str, Any] = {}
    citations: list[dict[str, Any]] = []
    context = ""
    from app.characters import resolve

    persona = persona_obj or resolve(persona_id, viewer)
    if course_id and should_retrieve(persona, question, course_id):
        debug = retrieve_for_course(course_id, question, store)
        final = debug.get("final") or []
        context, citations = build_context(final)
        debug = {
            "vector": _brief(debug.get("vector")),
            "bm25": _brief(debug.get("bm25")),
            "exact": _brief(debug.get("exact")),
            "fused": _brief(debug.get("fused")),
            "reranked": _brief(debug.get("reranked")),
            "rerank": debug.get("rerank"),
            "final": _brief(final),
        }

    weak: list[str] = []
    age_band = "adult"
    if course_id:
        course = store.get_course(course_id)
        if course:
            age_band = course.get("age_band") or "adult"
    if user_id and course_id:
        prog = store.list_progress(user_id, course_id)
        weak = [p["topic_name"] for p in prog if float(p.get("mastery_score") or 0) < 0.45][:5]

    messages = build_messages(
        persona_id=persona_id,
        question=question,
        history=history,
        context=context,
        weak_topics=weak,
        has_passages=bool(citations),
        age_band=age_band,
        persona=persona,
    )
    yield {"event": "meta", "citations": citations, "debug": debug, "persona": persona_id}

    pieces: list[str] = []
    for token in chat_stream(
        messages, temperature=persona.temperature, num_predict=num_predict
    ):
        pieces.append(token)
        yield {"event": "token", "text": token}

    raw = "".join(pieces)
    extra = 0
    while extra < 2 and needs_continue(raw):
        extra += 1
        tail = raw[-120:].replace("```", "` ` `")
        follow = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "You were cut off mid-code. Continue from this exact suffix only. "
                    "Do not restart the file. Close strings, parens, braces, and the "
                    f"Markdown fence:\n…{tail}"
                ),
            },
        ]
        for token in chat_stream(follow, temperature=0.2, num_predict=1024):
            pieces.append(token)
            yield {"event": "token", "text": token}
        raw = "".join(pieces)

    raw, quiz = extract_quiz(raw)
    cleaned, used = validate_citations(raw, len(citations))
    if extra:
        debug = dict(debug or {})
        debug["continued"] = extra
    kept = [c for c in citations if c["n"] in used]
    yield {
        "event": "done",
        "answer": cleaned,
        "citations": kept,
        "quiz": quiz,
        "debug": debug,
    }


def needs_continue(text: str) -> bool:
    """True when a reply looks truncated mid-code."""
    if not (text or "").strip():
        return False
    if text.count("```") % 2 == 1:
        return True
    last = ""
    for line in reversed(text.splitlines()):
        if line.strip():
            last = line.rstrip()
            break
    if not last:
        return False
    codeish = last[:1].isspace() or any(ch in last for ch in ";={}()[]")
    if last.endswith(("+", "=", ",", "(", "[", "{", '"', "\\")):
        return True
    if last.endswith("'") and codeish:
        return True
    if last.endswith(".") and codeish:
        return True
    if last.count("(") > last.count(")"):
        return True
    if last.count("{") > last.count("}"):
        return True
    if last.count("[") > last.count("]"):
        return True
    if last.count('"') % 2 == 1:
        return True
    if last.count("'") % 2 == 1 and any(ch in last for ch in "=("):
        return True
    return False


def _brief(items: list[dict[str, Any]] | None, n: int = 6) -> list[dict[str, Any]]:
    out = []
    for item in (items or [])[:n]:
        out.append(
            {
                "id": item.get("id"),
                "score": item.get("score"),
                "source_file": item.get("source_file"),
                "heading_path": item.get("heading_path"),
                "content_type": item.get("content_type"),
                "snippet": (item.get("text") or item.get("snippet") or "")[:160],
            }
        )
    return out
