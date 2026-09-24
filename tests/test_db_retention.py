from datetime import datetime, timedelta, timezone

import pytest

from app.db import Base, SessionLocal, engine, purge_expired_documents
from app.models import DocumentRecord
from app.security import encrypt_text


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_record(expires_at: datetime) -> str:
    db = SessionLocal()
    try:
        record = DocumentRecord(
            owner_session_id="test-session",
            filename="lease.txt",
            document_type="residential_lease",
            jurisdiction="CA",
            encrypted_text=encrypt_text("sample text"),
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id
    finally:
        db.close()


def test_purge_removes_expired_documents():
    expired_id = _make_record(datetime.now(timezone.utc) - timedelta(days=1))

    purged_count = purge_expired_documents()

    assert purged_count == 1
    db = SessionLocal()
    try:
        assert db.get(DocumentRecord, expired_id) is None
    finally:
        db.close()


def test_purge_keeps_documents_not_yet_expired():
    active_id = _make_record(datetime.now(timezone.utc) + timedelta(days=10))

    purged_count = purge_expired_documents()

    assert purged_count == 0
    db = SessionLocal()
    try:
        assert db.get(DocumentRecord, active_id) is not None
    finally:
        db.close()


def test_purge_only_removes_expired_leaves_active_untouched():
    expired_id = _make_record(datetime.now(timezone.utc) - timedelta(minutes=1))
    active_id = _make_record(datetime.now(timezone.utc) + timedelta(days=1))

    purge_expired_documents()

    db = SessionLocal()
    try:
        assert db.get(DocumentRecord, expired_id) is None
        assert db.get(DocumentRecord, active_id) is not None
    finally:
        db.close()
