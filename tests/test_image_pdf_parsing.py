import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import Base, engine
from app.main import app
from app.parsing import parse_document
from app.security import UploadValidationError, validate_upload


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_dummy_image(format: str = "PNG") -> bytes:
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_validate_upload_accepts_valid_png():
    png_bytes = _make_dummy_image("PNG")
    validate_upload("notice.png", png_bytes)


def test_validate_upload_accepts_valid_jpg():
    jpg_bytes = _make_dummy_image("JPEG")
    validate_upload("notice.jpg", jpg_bytes)


def test_validate_upload_rejects_spoofed_png():
    with pytest.raises(UploadValidationError, match="valid PNG image"):
        validate_upload("notice.png", b"not-a-png-file")


def test_validate_upload_rejects_spoofed_jpg():
    with pytest.raises(UploadValidationError, match="valid JPEG image"):
        validate_upload("notice.jpg", b"not-a-jpeg-file")


def test_parse_document_image():
    png_bytes = _make_dummy_image("PNG")
    text = parse_document("notice.png", png_bytes)
    assert len(text) > 20
    assert "NOTICE TO VACATE" in text


def test_api_upload_photo_and_analyze():
    client = TestClient(app)
    # 1. Start session
    session_res = client.post("/api/session")
    assert session_res.status_code == 200
    token = session_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload photo
    png_bytes = _make_dummy_image("PNG")
    upload_res = client.post(
        "/api/documents",
        files={"file": ("eviction_notice.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]
    assert upload_res.json()["document_type"] == "notice_to_vacate"

    # 3. Analyze document
    analysis_res = client.post(f"/api/documents/{doc_id}/analyze", headers=headers)
    assert analysis_res.status_code == 200
    data = analysis_res.json()
    assert data["document_type"] == "notice_to_vacate"
    assert data["tenant_protection_score"] > 0
