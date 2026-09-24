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
        expanded_terms = _get_expanded_query_terms(question)
        windows = [_best_window(chunk, expanded_terms) for chunk in top_chunks]

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


_LEGAL_SYNONYM_MAP: dict[str, set[str]] = {
    "deposit": {"security deposit", "damage deposit", "cleaning deposit", "rental bond", "holding deposit"},
    "notice": {"notice", "written notice", "notification", "in writing", "days notice", "advance notice"},
    "entry": {"entry", "access", "enter", "enter premises", "inspection", "show unit", "landlord entry"},
    "eviction": {"evict", "eviction", "vacate", "terminate tenancy", "quit", "unlawful detainer", "cure or quit"},
    "maintenance": {"maintenance", "repair", "repairs", "habitability", "condition of premises", "plumbing", "appliances"},
    "rent": {"rent", "monthly rent", "rental payment", "due date", "grace period", "late fee", "late charge"},
    "pet": {"pet", "pets", "animal", "animals", "dog", "cat", "service animal", "emotional support"},
    "sublease": {"sublease", "sublet", "assignment", "re-let", "transfer", "assign"},
    "guest": {"guest", "guests", "visitor", "visitors", "occupant", "unauthorized occupant"},
    "termination": {"early termination", "break lease", "surrender", "liquidated damages", "cancellation"},
    "landlord": {"landlord", "owner", "lessor", "property manager", "management"},
    "tenant": {"tenant", "renter", "lessee", "resident"},
}


def _expand_keywords(keywords: tuple[str, ...]) -> list[str]:
    """Expand rubric keywords with domain synonyms to enhance retrieval fidelity."""
    expanded = list(keywords)
    for kw in keywords:
        kw_lower = kw.lower()
        for syn_key, syn_set in _LEGAL_SYNONYM_MAP.items():
            if syn_key in kw_lower:
                for syn in syn_set:
                    if syn not in expanded:
                        expanded.append(syn)
    return expanded


def _find_excerpt(original_text: str, lowered_text: str, keywords: tuple[str, ...]) -> str | None:
    all_keywords = _expand_keywords(keywords)
    for kw in all_keywords:
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
    highest overlap with the distinctive query terms and domain synonyms.
    """
    direct_terms = {t for t in query_terms if t not in _STOPWORDS and len(t) >= 3}
    expanded = _get_expanded_query_terms(" ".join(query_terms))
    syn_only = {t for t in expanded if t not in _STOPWORDS and len(t) >= 3} - direct_terms

    normalized_chunk = re.sub(r"(?<!\n)\n(?!\n)", " ", chunk)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n{2,}", normalized_chunk) if s.strip()]
    if not sentences:
        return chunk.strip()[:width]

    def score_sentence(s: str) -> float:
        s_lower = s.lower()
        # Deprioritize contract boilerplate preambles ("is entered into between")
        penalty = -5.0 if "entered into between" in s_lower else 0.0
        # Boost operational metrics (numbers, hours, days, dollars)
        metric_boost = 2.0 if re.search(r'\b\d+\s*(?:hours|days|months|weeks|\$)\b', s_lower) else 0.0
        score = sum(3.0 for t in direct_terms if re.search(r'\b' + re.escape(t), s_lower))
        score += sum(1.5 for t in syn_only if re.search(r'\b' + re.escape(t), s_lower))
        return score + metric_boost + penalty

    best_sentence = max(sentences, key=score_sentence)
    if score_sentence(best_sentence) <= 0:
        return chunk.strip()[:width]

    idx = chunk.find(best_sentence)
    if idx == -1:
        # Match case-insensitively or on normalized text
        idx = normalized_chunk.find(best_sentence)
        if idx != -1:
            chunk = normalized_chunk

    if idx != -1:
        start = max(0, idx - 40)
        end = min(len(chunk), idx + len(best_sentence) + 80)
        return chunk[start:end].strip()

    return best_sentence[:width]


def _get_expanded_query_terms(question: str) -> set[str]:
    """Extract question terms and expand with legal synonyms for semantic retrieval."""
    q_lower = question.lower()
    q_terms = set(re.findall(r"[a-z']+", q_lower))
    expanded = set(q_terms)
    for term in q_terms:
        if term in _STOPWORDS or len(term) < 3:
            continue
        for syn_key, syn_set in _LEGAL_SYNONYM_MAP.items():
            if term == syn_key or term in syn_set or any(term == s.split()[0] for s in syn_set):
                expanded.add(syn_key)
                for syn in syn_set:
                    expanded.update(re.findall(r"[a-z']+", syn.lower()))
    return expanded


def _rank_chunks(question: str, chunks: list[str]) -> list[tuple[str, float]]:
    """Semantic overlap scorer supporting domain synonyms and term specificity.
    Simulates high-fidelity LLM retrieval during offline testing and air-gapped CI.
    """
    q_terms = set(re.findall(r"[a-z']+", question.lower()))
    expanded_terms = _get_expanded_query_terms(question)

    scored = []
    for chunk in chunks:
        c_terms = re.findall(r"[a-z']+", chunk.lower())
        direct_matches = sum(2.0 for t in c_terms if t in q_terms and t not in _STOPWORDS)
        syn_matches = sum(1.5 for t in c_terms if t in expanded_terms and t not in q_terms and t not in _STOPWORDS)
        score = (direct_matches + syn_matches) / (len(c_terms) + 1)
        scored.append((chunk, score))
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
