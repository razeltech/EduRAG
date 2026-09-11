"""Hybrid retrieval: vector + BM25 + exact-term boost. Optional rerank (degraded if missing)."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+(?:[./=_-][a-z0-9]+)*", re.I)
_QUOTED = re.compile(r"\"([^\"]+)\"|'([^']+)'")
RRF_K = 60


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


class BM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_len = [len(d) or 1 for d in corpus]
        self.avgdl = sum(self.doc_len) / max(len(corpus), 1)
        self.doc_freq: dict[str, int] = {}
        self.tf: list[Counter] = []
        for doc in corpus:
            counts = Counter(doc)
            self.tf.append(counts)
            for term in counts:
                self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
        self.n = max(len(corpus), 1)

    def scores(self, query: list[str]) -> list[float]:
        out = [0.0] * self.n
        for term in query:
            df = self.doc_freq.get(term)
            if not df:
                continue
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for i, counts in enumerate(self.tf):
                freq = counts.get(term, 0)
                if not freq:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                out[i] += idf * (freq * (self.k1 + 1)) / denom
        return out


def cosine_topk(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    if matrix is None or matrix.size == 0:
        return []
    scores = matrix @ query
    k = min(k, len(scores))
    idx = np.argpartition(scores, -k)[-k:]
    idx = idx[np.argsort(scores[idx])[::-1]]
    return [(int(i), float(scores[i])) for i in idx]


def exact_term_boost(query: str, chunks: list[dict[str, Any]]) -> list[tuple[int, float]]:
    quoted = [m.group(1) or m.group(2) for m in _QUOTED.finditer(query)]
    tokens = tokenize(query)
    specials = [t for t in tokens if any(ch in t for ch in "./=_-") or (t[:1].isalpha() and any(c.isdigit() for c in t))]
    needles = [q.lower() for q in quoted] + specials
    if not needles:
        return []
    hits: list[tuple[int, float]] = []
    for i, chunk in enumerate(chunks):
        text = (chunk.get("text") or "").lower()
        score = sum(2.0 if n in text else 0.0 for n in needles)
        if score:
            hits.append((i, score))
    hits.sort(key=lambda x: x[1], reverse=True)
    return hits


CODE_QUERY = re.compile(
    r"\b(code|script|api|function|class|method|csharp|c#|python|shader|transform|"
    r"how do i|snippet|example|compile|error)\b",
    re.I,
)


def heading_boost(query: str, chunks: list[dict[str, Any]]) -> list[tuple[int, float]]:
    q = set(tokenize(query))
    if not q:
        return []
    hits: list[tuple[int, float]] = []
    for i, chunk in enumerate(chunks):
        path = tokenize(
            " ".join(
                str(chunk.get(k) or "")
                for k in ("heading_path", "chapter", "section", "source_file")
            )
        )
        overlap = len(q & set(path))
        if overlap:
            hits.append((i, float(overlap)))
    hits.sort(key=lambda x: x[1], reverse=True)
    return hits


def prefers_code(query: str) -> bool:
    return bool(CODE_QUERY.search(query or ""))


def rrf(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def hybrid_search(
    query: str,
    query_vec: np.ndarray,
    chunks: list[dict[str, Any]],
    matrix: np.ndarray | None,
    *,
    candidate_k: int = 24,
    top_k: int = 8,
) -> dict[str, Any]:
    if not chunks:
        return {
            "vector": [],
            "bm25": [],
            "exact": [],
            "fused": [],
            "reranked": [],
            "rerank": "none",
            "final": [],
        }

    vec_hits = cosine_topk(query_vec, matrix, candidate_k) if matrix is not None else []
    bm25 = BM25([tokenize(c["text"]) for c in chunks])
    bm_scores = bm25.scores(tokenize(query))
    bm_rank = sorted(range(len(chunks)), key=lambda i: bm_scores[i], reverse=True)
    bm_rank = [i for i in bm_rank[:candidate_k] if bm_scores[i] > 0]
    exact = exact_term_boost(query, chunks)[:candidate_k]

    fused_pairs = rrf(
        [
            [i for i, _ in vec_hits],
            bm_rank,
            [i for i, _ in exact],
            [i for i, _ in heading_boost(query, chunks)[:candidate_k]],
        ]
    )
    if prefers_code(query):
        fused_pairs = [
            (
                i,
                s + (0.18 if (chunks[i].get("content_type") or "") == "code" else 0.0),
            )
            for i, s in fused_pairs
        ]
        fused_pairs.sort(key=lambda x: x[1], reverse=True)
    fused_idx = [i for i, _ in fused_pairs[:candidate_k]]
    from app.rerank import rerank

    reranked_pairs, rerank_kind = rerank(query, chunks, fused_pairs[:candidate_k], top_k=top_k)
    final_idx = [i for i, _ in reranked_pairs]

    def pack(pairs_or_idx: list, scores: dict[int, float] | None = None) -> list[dict[str, Any]]:
        out = []
        for item in pairs_or_idx:
            if isinstance(item, tuple):
                i, score = item
            else:
                i, score = item, (scores or {}).get(item, 0.0)
            chunk = dict(chunks[i])
            chunk["score"] = round(float(score), 4)
            chunk["rank_index"] = i
            out.append(chunk)
        return out

    fused_scores = dict(fused_pairs)
    rerank_scores = dict(reranked_pairs)
    return {
        "vector": pack(vec_hits),
        "bm25": pack([(i, bm_scores[i]) for i in bm_rank]),
        "exact": pack(exact),
        "fused": pack(fused_idx, fused_scores),
        "reranked": pack(reranked_pairs),
        "rerank": rerank_kind,
        "final": pack(final_idx, rerank_scores),
    }
