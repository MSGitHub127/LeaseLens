import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from tests.conftest import SAMPLE_LEASE, SAMPLE_NOTICE


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _auth_headers(client) -> dict:
    resp = client.post("/api/session")
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _upload(client, headers, filename="lease.txt", content=SAMPLE_LEASE.encode(), content_type="text/plain"):
    return client.post("/api/documents", headers=headers, files={"file": (filename, content, content_type)})


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_serves_frontend(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "LeaseLens" in resp.text
    assert "<html" in resp.text.lower()


def test_upload_requires_authentication(client):
    resp = client.post("/api/documents", files={"file": ("lease.txt", SAMPLE_LEASE.encode(), "text/plain")})
    assert resp.status_code == 401


def test_full_flow_upload_analyze_checklist_ask(client):
    headers = _auth_headers(client)

    upload_resp = _upload(client, headers)
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["document_id"]
    assert upload_resp.json()["document_type"] == "residential_lease"
    assert upload_resp.json()["jurisdiction"] == "CA"

    analyze_resp = client.post(f"/api/documents/{doc_id}/analyze", headers=headers)
    assert analyze_resp.status_code == 200
    body = analyze_resp.json()
    assert body["document_type"] == "residential_lease"
    assert len(body["findings"]) > 0
    assert isinstance(body["plain_language_summary"], str) and body["plain_language_summary"]

    checklist_resp = client.get(f"/api/documents/{doc_id}/checklist", headers=headers)
    assert checklist_resp.status_code == 200
    assert len(checklist_resp.json()["items"]) > 0

    ask_resp = client.post(
        f"/api/documents/{doc_id}/ask", headers=headers, json={"question": "how much notice before entry?"}
    )
    assert ask_resp.status_code == 200
    assert ask_resp.json()["grounded"] is True


def test_upload_rejects_disallowed_file_type(client):
    headers = _auth_headers(client)
    resp = _upload(client, headers, filename="lease.exe", content=b"MZ" + b"0" * 40, content_type="application/octet-stream")
    assert resp.status_code == 400


def test_upload_redacts_pii_before_storage(client):
    headers = _auth_headers(client)
    text_with_pii = SAMPLE_LEASE + "\nTenant email: jane.doe@example.com, phone 555-123-4567."
    resp = _upload(client, headers, content=text_with_pii.encode())
    assert resp.status_code == 201
    assert resp.json()["pii_redacted"].get("email") == 1
    assert resp.json()["pii_redacted"].get("phone") == 1

    # Confirm the raw PII never comes back out through any read endpoint either.
    doc_id = resp.json()["document_id"]
    analyze_resp = client.post(f"/api/documents/{doc_id}/analyze", headers=headers)
    assert "jane.doe@example.com" not in analyze_resp.text
    assert "555-123-4567" not in analyze_resp.text


def test_session_cannot_access_another_sessions_document(client):
    headers_a = _auth_headers(client)
    headers_b = _auth_headers(client)

    doc_id = _upload(client, headers_a).json()["document_id"]

    resp = client.get(f"/api/documents/{doc_id}", headers=headers_b)
    assert resp.status_code == 404  # not 403 -- avoids confirming existence to a non-owner


def test_invalid_token_rejected(client):
    resp = client.get("/api/documents/some-id", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_compare_two_documents(client):
    headers = _auth_headers(client)
    doc_a = _upload(client, headers, filename="lease_a.txt").json()["document_id"]
    doc_b = _upload(client, headers, filename="lease_b.txt", content=(SAMPLE_LEASE + "\nAdditional clause.").encode()).json()["document_id"]

    resp = client.post("/api/documents/compare", headers=headers, json={"document_id_a": doc_a, "document_id_b": doc_b})
    assert resp.status_code == 200
    assert "diffs" in resp.json()


def test_delete_document(client):
    headers = _auth_headers(client)
    doc_id = _upload(client, headers).json()["document_id"]

    del_resp = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert get_resp.status_code == 404


def test_notice_document_gets_notice_specific_findings(client):
    headers = _auth_headers(client)
    doc_id = _upload(client, headers, filename="notice.txt", content=SAMPLE_NOTICE.encode()).json()["document_id"]
    resp = client.post(f"/api/documents/{doc_id}/analyze", headers=headers)
    rule_ids = {f["rule_id"] for f in resp.json()["findings"]}
    assert "notice_response_deadline" in rule_ids
    assert "security_deposit_terms" not in rule_ids  # lease-only rule shouldn't apply here
