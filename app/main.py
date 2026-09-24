from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db, purge_expired_documents
from app.routers import analysis, documents, qa, session

# Structured logging that never includes document content or PII -- only
# request metadata. This is a deliberate privacy choice: see app/security.py
# for where redaction happens before anything is stored or logged.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("leaselens")


def create_app() -> FastAPI:
    settings = get_settings()

    if settings.environment == "production" and settings.secret_key == "dev-only-insecure-secret-change-me":
        raise RuntimeError(
            "Refusing to start in production with the default secret key. "
            "Set LEASELENS_SECRET_KEY to a strong random value."
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        purged = purge_expired_documents()
        if purged:
            logger.info("Purged %d expired document(s) on startup.", purged)
        yield

    app = FastAPI(
        title=settings.app_name,
        description="Context-aware assistant for understanding tenancy documents. "
                     "Provides information and organization, not legal advice.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' data:; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' http://localhost:8000 https:; "
            "frame-ancestors 'self' *;"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    app.include_router(session.router)
    app.include_router(documents.router)
    app.include_router(analysis.router)
    app.include_router(qa.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internal error detail (stack traces, file paths, doc
        # content) to the client -- log server-side, return a generic message.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error."})

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    # Mount static frontend files for all-in-one container deployment
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.isdir(frontend_dir):
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
