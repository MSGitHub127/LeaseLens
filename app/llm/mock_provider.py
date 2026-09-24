"""
A fully offline, deterministic provider. This is the default provider (see
app/config.py: LEASELENS_LLM_PROVIDER=mock) so the app is demoable and fully
testable without any API key or network access -- important for a hackathon
judge who just wants to `docker compose up` and click around, and for CI,
which should never depend on a paid external call.

It implements the same contract as the real Anthropic-backed provider
(app/llm/anthropic_provider.py), just with keyword/heuristic logic instead of
model calls. Swapping providers is a one-line config change.
"""
from __future__ import annotations

import re

from app.llm.provider import ClauseFinding, LLMProvider, QAAnswer
from app.rubric import Rubric, RubricRule

_ADVICE_INTENT_PATTERNS = (
    r"\bshould i\b", r"\bcan i sue\b", r"\bis this legal\b", r"\bis it legal\b",
    r"\bam i required\b", r"\bwhat should i do\b", r"\bcan they\b", r"\bis this enforceable\b",
)


class MockProvider(LLMProvider):
    def extract_clauses(self, document_text: str, rubric: Rubric) -> list[ClauseFinding]:
        lowered = document_text.lower()
        findings: list[ClauseFinding] = []
        for rule in rubric.rules:
            excerpt = _find_excerpt(document_text, lowered, rule.keywords)
            present = excerpt is not None
            findings.append(
                ClauseFinding(
                    rule_id=rule.id,
                    title=rule.title,
                    present=present,
                    severity="info" if present else rule.severity_if_absent,
                    excerpt=excerpt,
                    explanation=_explain(rule, present, rubric),
                )
            )
        return findings

    def answer_question(self, question: str, context_chunks: list[str], rubric: Rubric) -> QAAnswer:
        scored = _rank_chunks(question, context_chunks)
        top_chunks = [c for c, score in scored[:3] if score > 0]

        is_advice = bool(re.search("|".join(_ADVICE_INTENT_PATTERNS), question.lower()))
        disclaimer = None
        if is_advice:
            disclaimer = (
                "This is general information based on your document, not legal advice. "
                "For guidance specific to your situation, consider a tenant rights "
                "clinic or a licensed attorney in your state."
            )

        if not top_chunks:
            return QAAnswer(
                answer="I couldn't find anything in this document that addresses that question. "
                       "It may not be covered by this lease, or try rephrasing.",
                grounded=False,
                citations=[],
                disclaimer=disclaimer,
            )

        # Extract a window centered on the actual matching terms rather than
        # blindly taking a chunk's opening characters -- a chunk can be large
        # and the relevant sentence may be buried well past the start.
        q_terms = set(re.findall(r"[a-z']+", question.lower()))
        windows = [_best_window(chunk, q_terms) for chunk in top_chunks]

        answer = "Based on this document: " + " (...) ".join(windows)
        return QAAnswer(answer=answer, grounded=True, citations=windows, disclaimer=disclaimer)

    def plain_language_summary(self, document_text: str, findings: list[ClauseFinding]) -> str:
        missing = [f for f in findings if not f.present and f.severity in ("high", "medium")]
        present_count = sum(1 for f in findings if f.present)
        lines = [
            f"This document covers {present_count} of {len(findings)} common items I checked for.",
        ]
        if missing:
            lines.append(
                "A few things worth asking about before you sign: "
                + "; ".join(f.title for f in missing[:3])
                + "."
            )
        else:
            lines.append("The common items I checked for all appear to be addressed somewhere in the text.")
        return " ".join(lines)

    def extract_text_from_image(self, image_bytes: bytes, mime_type: str) -> str:
        # Deterministic mock image extraction for tests & offline development
        return (
            "NOTICE TO VACATE\n\n"
            "This notice to vacate is served to the tenant for non-payment of rent. "
            "You have 3 days to cure the violation by paying the outstanding balance in full, "
            "or you must vacate the premises by the deadline: March 31. "
            "Failure to vacate will result in legal proceedings."
        )


def _find_excerpt(original_text: str, lowered_text: str, keywords: tuple[str, ...]) -> str | None:
    for kw in keywords:
        idx = lowered_text.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 60)
            end = min(len(original_text), idx + len(kw) + 80)
            return original_text[start:end].strip()
    return None


def _explain(rule: RubricRule, present: bool, rubric: Rubric) -> str:
    if present:
        return f"Found language addressing this. {rule.guidance}"
    state_note = ""
    if rubric.jurisdiction and rubric.state_parameters.get("note"):
        state_note = f" Note for {rubric.jurisdiction}: {rubric.state_parameters['note']}"
    return f"No matching language found in the document. {rule.guidance}{state_note}"


_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "how", "what", "when", "where",
    "before", "after", "much", "many", "does", "do", "did", "can", "will", "would",
    "this", "that", "and", "for", "with", "about", "from",
}


def _best_window(chunk: str, query_terms: set[str], width: int = 220) -> str:
    """Return the sentence (with a little surrounding context) that has the
    highest overlap with the *distinctive* query terms.

    Ranking by density of matches (rather than by "earliest occurrence of
    any term") avoids getting stuck on a common word like "landlord" that
    happens to appear in the chunk's first sentence but has nothing to do
    with what's actually being asked.
    """
    meaningful_terms = {t for t in query_terms if t not in _STOPWORDS and len(t) >= 3}
    if not meaningful_terms:
        meaningful_terms = query_terms

    sentences = re.split(r"(?<=[.!?])\s+|\n+", chunk)
    sentences = [s for s in sentences if s.strip()]
    if not sentences:
        return chunk.strip()[:width]

    def score(sentence: str) -> int:
        lowered = sentence.lower()
        return sum(1 for term in meaningful_terms if term in lowered)

    best_sentence = max(sentences, key=score)
    if score(best_sentence) == 0:
        return chunk.strip()[:width]

    idx = chunk.find(best_sentence)
    start = max(0, idx - 40)
    end = min(len(chunk), idx + len(best_sentence) + 80)
    return chunk[start:end].strip()


def _rank_chunks(question: str, chunks: list[str]) -> list[tuple[str, float]]:
    """Very small bag-of-words overlap scorer -- see app/rag.py for the
    slightly richer TF-based version used by the real retrieval path. Kept
    self-contained here so MockProvider has zero dependency on other modules'
    internals and is trivially unit-testable in isolation.
    """
    q_terms = set(re.findall(r"[a-z']+", question.lower()))
    scored = []
    for chunk in chunks:
        c_terms = re.findall(r"[a-z']+", chunk.lower())
        overlap = sum(1 for t in c_terms if t in q_terms)
        scored.append((chunk, overlap / (len(c_terms) + 1)))
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
