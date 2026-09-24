import pytest

from app.security import (
    UploadValidationError,
    decrypt_text,
    encrypt_text,
    redact_pii,
    validate_upload,
)


def test_validate_upload_accepts_valid_pdf_header():
    validate_upload("lease.pdf", b"%PDF-1.4 rest of a fake pdf body that is long enough")


def test_validate_upload_rejects_disallowed_extension():
    with pytest.raises(UploadValidationError, match="Unsupported file type"):
        validate_upload("lease.exe", b"MZ" + b"0" * 50)


def test_validate_upload_rejects_oversized_file(monkeypatch):
    from app import security

    settings = security.get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    with pytest.raises(UploadValidationError, match="exceeds"):
        validate_upload("lease.txt", b"0123456789ABCDEF")


def test_validate_upload_rejects_empty_file():
    with pytest.raises(UploadValidationError, match="empty"):
        validate_upload("lease.txt", b"")


def test_validate_upload_rejects_spoofed_pdf():
    with pytest.raises(UploadValidationError, match="valid PDF"):
        validate_upload("lease.pdf", b"this is not actually a pdf, just text pretending to be one")


def test_validate_upload_rejects_missing_extension():
    with pytest.raises(UploadValidationError, match="valid extension"):
        validate_upload("lease", b"some content")


@pytest.mark.parametrize(
    "text,label",
    [
        ("Contact me at jane.doe@example.com for questions.", "email"),
        ("Call me at (555) 123-4567 anytime.", "phone"),
        ("My SSN is 123-45-6789.", "ssn"),
    ],
)
def test_redact_pii_removes_known_categories(text, label):
    redacted, counts = redact_pii(text)
    assert label in counts
    assert counts[label] >= 1
    assert f"[REDACTED_{label.upper()}]" in redacted


def test_redact_pii_leaves_ordinary_text_untouched():
    text = "The tenant shall pay rent on the first of each month."
    redacted, counts = redact_pii(text)
    assert redacted == text
    assert counts == {}


def test_redact_pii_handles_multiple_categories_at_once():
    text = "Email jane@example.com or call 555-123-4567. SSN: 987-65-4321."
    redacted, counts = redact_pii(text)
    assert counts.get("email") == 1
    assert counts.get("ssn") == 1
    assert "jane@example.com" not in redacted
    assert "987-65-4321" not in redacted


def test_encrypt_decrypt_roundtrip():
    original = "Sensitive lease text that should never be stored in plaintext."
    token = encrypt_text(original)
    assert token != original.encode()
    assert decrypt_text(token) == original
