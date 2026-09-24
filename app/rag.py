"""
Minimal, dependency-free retrieval over document chunks. Deliberately not
using a vector database or embeddings API for this scale of document (a
lease is a few thousand words, not a corpus) -- a term-frequency cosine
score is fast, has zero external dependency, is fully deterministic (good
for tests), and is easy to audit. Swap in a real embedding index if this
ever needs to scale to multi-document corpora.
"""
from __future__ import annotations

import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _stem(token: str) -> str:
    """Lightweight suffix normalization for common legal / tenancy terms."""
    if len(token) <= 3:
        return token
    for suffix in ("ation", "ement", "ments", "ting", "tion", "ing", "ies", "ed", "es", "ate", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            if suffix == "ies":
                return base + "y"
            return base
    return token


_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "with",
    "by", "of", "and", "or", "it", "this", "that", "can", "i", "my", "me", "we", "you", "be"
}


def _term_freqs(tokens: list[str]) -> Counter:
    counts: Counter = Counter()
    for t in tokens:
        weight = 0.05 if t in _STOPWORDS else 2.0
        counts[t] += weight
        stemmed = _stem(t)
        if stemmed != t:
            stem_weight = 0.02 if t in _STOPWORDS else 1.0
            counts[stemmed] += stem_weight
    return counts


def _cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_relevant_chunks(query: str, chunks: list[str], top_k: int = 4) -> list[str]:
    """Return up to top_k chunks most relevant to query, ranked by TF cosine similarity.

    Includes morphological normalization so questions like 'can I terminate?'
    reliably match document clauses titled 'Termination of Tenancy', while maintaining
    strict grounding: chunks without substantive term overlap are excluded.
    """
    if not chunks:
        return []
    q_tokens = _tokenize(query)
    q_meaningful = {t for t in q_tokens if t not in _STOPWORDS and len(t) > 2}
    q_stems = {_stem(t) for t in q_meaningful}

    q_vec = _term_freqs(q_tokens)
    scored = []
    for chunk in chunks:
        c_tokens = _tokenize(chunk)
        if q_meaningful:
            c_meaningful = {t for t in c_tokens if t not in _STOPWORDS}
            c_stems = {_stem(t) for t in c_meaningful}
            if not (q_meaningful & c_meaningful) and not (q_stems & c_stems):
                continue
        score = _cosine(q_vec, _term_freqs(c_tokens))
        if score > 0:
            scored.append((chunk, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [chunk for chunk, _ in scored[:top_k]]
