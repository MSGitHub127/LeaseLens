"""
Abstract interface every LLM backend implements. Keeping this boundary
explicit means:

  - Tests and CI run fully offline against MockProvider (deterministic, free,
    fast -- see app/llm/mock_provider.py).
  - Swapping providers (Anthropic today, something else tomorrow) never
    touches business logic in extraction.py / qa.py / checklist.py.
  - Every provider is required to return *structured, grounded* data --
    there's no code path where free-text LLM output reaches the user
    unvalidated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.rubric import Rubric


@dataclass
class ClauseFinding:
    rule_id: str
    title: str
    present: bool
    severity: str  # "high" | "medium" | "low" | "info"
    excerpt: str | None  # short grounding excerpt from the source document, or None
    explanation: str  # plain-language explanation


@dataclass
class QAAnswer:
    answer: str
    grounded: bool  # False if the model could not find support in the document
    citations: list[str]  # short excerpts the answer is based on
    disclaimer: str | None  # populated when the question sought legal advice


class LLMProvider(ABC):
    @abstractmethod
    def extract_clauses(self, document_text: str, rubric: Rubric) -> list[ClauseFinding]:
        """Evaluate the rubric's rules against the document text."""

    @abstractmethod
    def answer_question(self, question: str, context_chunks: list[str], rubric: Rubric) -> QAAnswer:
        """Answer strictly from context_chunks; never invent facts not in the document."""

    @abstractmethod
    def plain_language_summary(self, document_text: str, findings: list[ClauseFinding]) -> str:
        """Produce a short, plain-language (~8th-grade reading level) summary."""

    @abstractmethod
    def extract_text_from_image(self, image_bytes: bytes, mime_type: str) -> str:
        """Transcribe and extract text from an image or photo of a tenancy document."""
