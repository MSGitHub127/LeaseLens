from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_session
from app.classification import classify_document
from app.db import get_db
from app.deps import enforce_rate_limit
from app.models import DocumentRecord
from app.parsing import ParsingError, parse_document
from app.security import UploadValidationError, encrypt_text, redact_pii, validate_upload

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
    _: None = Depends(enforce_rate_limit),
) -> dict:
    content = await file.read()

    try:
        validate_upload(file.filename or "", content)
        text = parse_document(file.filename or "", content)
    except (UploadValidationError, ParsingError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # PII is redacted BEFORE storage and before it could ever be forwarded to
    # an LLM provider or logged -- see app/security.py.
    redacted_text, pii_counts = redact_pii(text)
    classification = classify_document(redacted_text)

    record = DocumentRecord(
        owner_session_id=session_id,
        filename=file.filename or "document",
        document_type=classification.document_type.value,
        jurisdiction=classification.jurisdiction,
        encrypted_text=encrypt_text(redacted_text),
        pii_redaction_counts=json.dumps(pii_counts),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "document_id": record.id,
        "filename": record.filename,
        "document_type": record.document_type,
        "jurisdiction": record.jurisdiction,
        "pii_redacted": pii_counts,
    }


@router.get("/{document_id}")
def get_document(
    document_id: str,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    record = _get_owned_document(db, document_id, session_id)
    return {
        "document_id": record.id,
        "filename": record.filename,
        "document_type": record.document_type,
        "jurisdiction": record.jurisdiction,
        "created_at": record.created_at.isoformat(),
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_document(
    document_id: str,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> None:
    record = _get_owned_document(db, document_id, session_id)
    db.delete(record)
    db.commit()


def _get_owned_document(db: Session, document_id: str, session_id: str) -> DocumentRecord:
    record = db.get(DocumentRecord, document_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    # Ownership check: a session may only ever access documents it uploaded.
    # Returning 404 (not 403) avoids confirming the document exists at all.
    if record.owner_session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return record
