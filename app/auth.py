"""
Authentication model: LeaseLens deliberately does not require an account or
collect a name/email to use the tool (privacy-by-design for a sensitive-data
product). Instead, a client gets an anonymous, short-lived signed session
token on first use; every document and query is scoped to that session id,
so one browser session can never read another's uploaded documents even
though no personal identity is attached to either.

For a production deployment with persistent user accounts, swap
`create_session_token`/`get_current_session` for a real user-auth flow --
the rest of the app only depends on "a session id string", so the change is
localized to this file.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)
_ALGORITHM = "HS256"


def create_session_token(session_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.token_expire_minutes)
    payload = {"sub": session_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing session token.")
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session token.") from exc
    session_id = payload.get("sub")
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token.")
    return session_id
