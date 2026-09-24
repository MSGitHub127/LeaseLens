"""
Classify *what kind* of tenancy document this is and *which jurisdiction* it
likely falls under. This is the first "context" signal that downstream logic
(app/rubric.py) uses to change its behavior -- a sublease is checked against
different rules than a notice to vacate, and a California lease is checked
against different deposit caps than a Texas one.

Deliberately rule-based (not an LLM call): classification needs to be fast,
free, deterministic, and testable, and a handful of keyword signals is enough
to route to the right rubric with high confidence. The LLM budget is spent
where it adds real value: clause-level explanation and free-form Q&A.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DocumentType(str, Enum):
    RESIDENTIAL_LEASE = "residential_lease"
    SUBLEASE = "sublease"
    ROOMMATE_AGREEMENT = "roommate_agreement"
    NOTICE_TO_VACATE = "notice_to_vacate"
    LEASE_ADDENDUM = "lease_addendum"
    UNKNOWN = "unknown"


_TYPE_KEYWORDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.SUBLEASE: ("sublease", "sublessor", "sublessee", "subtenant"),
    DocumentType.ROOMMATE_AGREEMENT: ("roommate agreement", "co-tenant agreement", "shared housing agreement"),
    DocumentType.NOTICE_TO_VACATE: ("notice to vacate", "notice to quit", "termination of tenancy", "eviction notice"),
    DocumentType.LEASE_ADDENDUM: ("addendum", "amendment to lease", "lease modification"),
    DocumentType.RESIDENTIAL_LEASE: ("lease agreement", "rental agreement", "landlord", "tenant", "leased premises"),
}

# Ordered by specificity: check the more specific types before falling back
# to the generic residential lease bucket.
_TYPE_PRIORITY = (
    DocumentType.NOTICE_TO_VACATE,
    DocumentType.SUBLEASE,
    DocumentType.ROOMMATE_AGREEMENT,
    DocumentType.LEASE_ADDENDUM,
    DocumentType.RESIDENTIAL_LEASE,
)

_STATE_NAMES = {
    "california": "CA", "new york": "NY", "texas": "TX", "florida": "FL",
    "illinois": "IL", "washington": "WA", "massachusetts": "MA", "georgia": "GA",
}
_STATE_ABBR = {" ca ", " ny ", " tx ", " fl ", " il ", " wa ", " ma ", " ga "}


@dataclass
class ClassificationResult:
    document_type: DocumentType
    type_confidence: float  # 0..1, based on keyword hit density
    jurisdiction: str | None  # two-letter state code, or None if undetermined
    jurisdiction_confidence: float


def classify_document(text: str) -> ClassificationResult:
    lowered = text.lower()

    doc_type = DocumentType.UNKNOWN
    confidence = 0.0
    for candidate in _TYPE_PRIORITY:
        hits = sum(1 for kw in _TYPE_KEYWORDS[candidate] if kw in lowered)
        if hits > 0:
            doc_type = candidate
            # confidence grows with hits but saturates; purely heuristic.
            confidence = min(1.0, 0.5 + 0.2 * hits)
            break

    jurisdiction, jur_conf = _detect_jurisdiction(lowered)

    return ClassificationResult(
        document_type=doc_type,
        type_confidence=confidence,
        jurisdiction=jurisdiction,
        jurisdiction_confidence=jur_conf,
    )


def _detect_jurisdiction(lowered_text: str) -> tuple[str | None, float]:
    for name, abbr in _STATE_NAMES.items():
        if name in lowered_text:
            return abbr, 0.9
    padded = f" {lowered_text} "
    for token in _STATE_ABBR:
        if token in padded:
            return token.strip().upper(), 0.5
    return None, 0.0
