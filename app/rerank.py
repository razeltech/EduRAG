"""Second-stage rerank. Uses a local cross-encoder if present, else lexical features."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config_load import load_config
from app.retrieve import heading_boost, tokenize


def rerank_available() -> tuple[bool, str]:
    cfg = load_config()
    block = cfg.get("reranker") or {}
    path = block.get("path")
    if path and Path(path).exists() and block.get("enabled"):
        return True, "cross-encoder"
    return False, "lexical"


def lexical_rerank(
    query: str,
    chunks: list[dict[str, Any]],
    fused: list[tuple[int, float]],
    *,
    top_k: int,
) -> list[tuple[int, float]]:
    qtok = set(tokenize(query))
    heading_hits = {i: s for i, s in heading_boost(query, chunks)}
    scored: list[tuple[int, float]] = []
    for i, base in fused:
        text = chunks[i].get("text") or ""
        cover = len(qtok & set(tokenize(text))) / max(len(qtok), 1)
        head = 0.12 if i in heading_hits else 0.0
        code_hit = 0.08 if (chunks[i].get("content_type") or "") == "code" and cover > 0 else 0.0
        scored.append((i, float(base) + 0.4 * cover + head + code_hit))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def rerank(
    query: str,
    chunks: list[dict[str, Any]],
    fused: list[tuple[int, float]],
    *,
    top_k: int,
) -> tuple[list[tuple[int, float]], str]:
    """Return (index, score) pairs and which strategy ran."""
    ok, kind = rerank_available()
    if ok and kind == "cross-encoder":
        try:
            pairs = _cross_encoder_scores(query, chunks, [i for i, _ in fused[:24]])
            if pairs:
                return pairs[:top_k], "cross-encoder"
        except Exception:
            pass
    return lexical_rerank(query, chunks, fused, top_k=top_k), "lexical"


def _cross_encoder_scores(
    query: str, chunks: list[dict[str, Any]], indices: list[int]
) -> list[tuple[int, float]] | None:
    """Optional: sentence-transformers CrossEncoder if the folder is a HF model."""
    cfg = load_config()
    path = (cfg.get("reranker") or {}).get("path")
    if not path:
        return None
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except ImportError:
        return None
    model = CrossEncoder(path)
    pairs = [(query, (chunks[i].get("text") or "")[:1200]) for i in indices]
    scores = model.predict(pairs)
    ranked = sorted(zip(indices, [float(s) for s in scores]), key=lambda x: x[1], reverse=True)
    return ranked
