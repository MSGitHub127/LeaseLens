from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class DocumentRecord(Base):
    """A stored document. `encrypted_text` holds Fernet-encrypted plaintext --
    never the raw uploaded file, and never plaintext at rest. Rows are purged
    after `document_retention_days` (app/config.py) by a scheduled task.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    owner_session_id: Mapped[str] = mapped_column(String, index=True)
    filename: Mapped[str] = mapped_column(String)
    document_type: Mapped[str] = mapped_column(String)
    jurisdiction: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_text: Mapped[bytes] = mapped_column(LargeBinary)
    pii_redaction_counts: Mapped[str] = mapped_column(String, default="{}")  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: _now() + timedelta(days=get_settings().document_retention_days),
    )


# --- API schemas -----------------------------------------------------------

class ClauseFindingOut(BaseModel):
    rule_id: str
    title: str
    present: bool
    severity: str
    excerpt: str | None
    explanation: str
    category: str | None = None


class AnalysisOut(BaseModel):
    document_id: str
    document_type: str
    document_type_confidence: float
    jurisdiction: str | None
    jurisdiction_confidence: float
    findings: list[ClauseFindingOut]
    plain_language_summary: str
    high_risk_count: int
    medium_risk_count: int
    tenant_protection_score: int = 100
    category_scores: dict[str, int] = {}


class ConsultationBriefOut(BaseModel):
    document_id: str
    document_type: str
    jurisdiction: str | None
    tenant_protection_score: int
    brief_markdown: str


class QuestionIn(BaseModel):
    question: str


class AnswerOut(BaseModel):
    answer: str
    grounded: bool
    citations: list[str]
    disclaimer: str | None


class ChecklistItemOut(BaseModel):
    priority: str  # "ask_before_signing" | "confirm_in_writing" | "good_to_know"
    text: str


class ChecklistOut(BaseModel):
    document_id: str
    items: list[ChecklistItemOut]


class CompareRequestIn(BaseModel):
    document_id_a: str
    document_id_b: str


class CompareRuleDiffOut(BaseModel):
    rule_id: str
    title: str
    status_a: str  # "present" | "absent"
    status_b: str
    changed: bool


class CompareOut(BaseModel):
    document_id_a: str
    document_id_b: str
    diffs: list[CompareRuleDiffOut]
    summary: str
