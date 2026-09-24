from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_session
from app.db import get_db
from app.deps import enforce_rate_limit
from app.models import AnswerOut, QuestionIn
from app.routers.documents import _get_owned_document
from app.classification import classify_document
from app.qa import answer_question
from app.rubric import get_rubric
from app.security import decrypt_text, sanitize_user_input

router = APIRouter(prefix="/api", tags=["qa"])


@router.post("/documents/{document_id}/ask", response_model=AnswerOut)
def ask(
    document_id: str,
    body: QuestionIn,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
    _: None = Depends(enforce_rate_limit),
) -> AnswerOut:
    record = _get_owned_document(db, document_id, session_id)
    text = decrypt_text(record.encrypted_text)
    classification = classify_document(text)
    rubric = get_rubric(classification.document_type, classification.jurisdiction)

    clean_question = sanitize_user_input(body.question)
    result = answer_question(text, clean_question, rubric)
    return AnswerOut(answer=result.answer, grounded=result.grounded, citations=result.citations, disclaimer=result.disclaimer)
