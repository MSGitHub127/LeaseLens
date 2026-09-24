from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.security import get_rate_limiter


def enforce_rate_limit(request: Request) -> None:
    limiter = get_rate_limiter()
    client_key = request.client.host if request.client else "unknown"
    if not limiter.allow(client_key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please slow down.")
