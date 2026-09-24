from __future__ import annotations

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


def analyze_document(text: str) -> AnalysisResult:
    """The core pipeline: classify context, select the matching rubric, then
    run extraction against it. This is the function that makes the
    assistant's behavior *depend on* what kind of document and jurisdiction
    it's looking at, rather than applying one static checklist to everything.
    """
    classification = classify_document(text)
    rubric = get_rubric(classification.document_type, classification.jurisdiction)

    provider = get_llm_provider()
    findings = provider.extract_clauses(text, rubric)
    summary = provider.plain_language_summary(text, findings)

    return AnalysisResult(
        classification=classification,
        rubric=rubric,
        findings=findings,
        plain_language_summary=summary,
    )
