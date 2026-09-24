from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.auth import create_session_token

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/session")
def create_session() -> dict:
    """Issue a new anonymous session token. No personal information is
    collected or required -- see app/auth.py for the rationale.
    """
    session_id = str(uuid.uuid4())
    token = create_session_token(session_id)
    return {"access_token": token, "token_type": "bearer"}
