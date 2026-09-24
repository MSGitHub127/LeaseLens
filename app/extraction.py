from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.classification import ClassificationResult, classify_document
from app.llm import get_llm_provider
from app.llm.provider import ClauseFinding
from app.rubric import Rubric, calculate_tenant_protection_score, get_rubric


@dataclass
class AnalysisResult:
    classification: ClassificationResult
    rubric: Rubric
    findings: list[ClauseFinding]
    plain_language_summary: str

    @property
    def high_risk_count(self) -> int:
        return sum(1 for f in self.findings if not f.present and f.severity == "high")

    @property
    def medium_risk_count(self) -> int:
        return sum(1 for f in self.findings if not f.present and f.severity == "medium")

    @property
    def tenant_protection_score(self) -> int:
        score, _ = calculate_tenant_protection_score(self.findings, self.rubric)
        return score

    @property
    def category_scores(self) -> dict[str, int]:
        _, breakdown = calculate_tenant_protection_score(self.findings, self.rubric)
        return breakdown


_ANALYSIS_CACHE: dict[str, AnalysisResult] = {}
_MAX_CACHE_SIZE = 128


def analyze_document(text: str) -> AnalysisResult:
    """The core pipeline: classify context, select the matching rubric, then
    run extraction against it. Uses SHA-256 memoization for sub-millisecond
    cached responses on subsequent checklist and brief generation calls.
    """
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if text_hash in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE[text_hash]

    classification = classify_document(text)
    rubric = get_rubric(classification.document_type, classification.jurisdiction)

    provider = get_llm_provider()
    findings = provider.extract_clauses(text, rubric)
    summary = provider.plain_language_summary(text, findings)

    result = AnalysisResult(
        classification=classification,
        rubric=rubric,
        findings=findings,
        plain_language_summary=summary,
    )

    if len(_ANALYSIS_CACHE) >= _MAX_CACHE_SIZE:
        _ANALYSIS_CACHE.pop(next(iter(_ANALYSIS_CACHE)))
    _ANALYSIS_CACHE[text_hash] = result
    return result
