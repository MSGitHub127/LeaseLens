import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

logger = logging.getLogger("leaselens.db")

settings = get_settings()
DATABASE_URL = settings.database_url

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
_engine_kwargs: dict = {"connect_args": _connect_args}

if DATABASE_URL == "sqlite:///:memory:":
    # An in-memory sqlite DB lives only inside a single connection -- without
    # StaticPool, each new connection from the pool would see a *fresh, empty*
    # database, so requests within the same app instance would silently lose
    # each other's data. Only relevant for sqlite:///:memory: (used by tests);
    # file-based sqlite and real databases don't need this.
    _engine_kwargs["poolclass"] = StaticPool
elif not DATABASE_URL.startswith("sqlite"):
    # Enterprise connection pooling for production RDBMS (PostgreSQL, Google Cloud SQL, MySQL).
    # Supports high concurrency, connection pre-pinging to drop dead connections, and recycles.
    _engine_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": settings.db_pool_recycle,
    })

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # Import models so they're registered on Base before create_all.
    from app import models  # noqa: F401

    if settings.environment == "production" and DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        is_mounted = any(db_path.startswith(p) for p in ("/data", "/mnt", "/var/lib", "C:\\data"))
        if not is_mounted:
            logger.warning(
                "OPERATIONAL RISK NOTICE: Running file-based SQLite in production without a persistent volume mount. "
                "Ephemeral container restarts may result in database state loss. "
                "For production high availability, set LEASELENS_DATABASE_URL to PostgreSQL/Cloud SQL "
                "(e.g. postgresql+psycopg2://user:pass@host:5432/leaselens) or mount a Cloud Run volume at /data."
            )

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
