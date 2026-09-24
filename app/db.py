from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.environ.get("LEASELENS_DATABASE_URL", "sqlite:///./leaselens.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# An in-memory sqlite DB lives only inside a single connection -- without
# StaticPool, each new connection from the pool would see a *fresh, empty*
# database, so requests within the same app instance would silently lose
# each other's data. Only relevant for sqlite:///:memory: (used by tests);
# file-based sqlite and real databases don't need this.
_engine_kwargs = {"connect_args": _connect_args}
if DATABASE_URL == "sqlite:///:memory:":
    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # Import models so they're registered on Base before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def purge_expired_documents() -> int:
    """Delete documents past their retention window. Called on startup and
    can be wired to a periodic scheduler (e.g. APScheduler, a cron job, or a
    Cloud Run scheduled job) in a real deployment.
    """
    from datetime import datetime, timezone

    from app.models import DocumentRecord

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = db.query(DocumentRecord).filter(DocumentRecord.expires_at < now).all()
        count = len(expired)
        for row in expired:
            db.delete(row)
        db.commit()
        return count
    finally:
        db.close()
