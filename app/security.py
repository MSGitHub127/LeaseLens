"""
Security-sensitive utilities, kept in one auditable module rather than spread
across the codebase:

  1. Upload validation      - reject dangerous/oversized files before parsing.
  2. PII redaction           - strip personal identifiers before text is ever
                                sent to an LLM provider or written to logs.
  3. Encryption at rest      - documents are stored encrypted (Fernet/AES128).
  4. Rate limiting           - simple in-memory sliding-window limiter.

None of this replaces a real security review, but it demonstrates the
defense-in-depth a legal-document tool needs: this app routinely handles
sensitive personal and financial text.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from cryptography.fernet import Fernet

from app.config import get_settings


class UploadValidationError(ValueError):
    """Raised when an uploaded file fails validation. Safe to show to users."""


def validate_upload(filename: str, content: bytes) -> None:
    """Validate a file before it is ever parsed.

    Guards against: disallowed types, oversized payloads, and empty/corrupt
    uploads. Parsing untrusted binary formats (PDF/DOCX) is itself an attack
    surface, so we fail fast and loud rather than handing garbage to a parser.
    """
    settings = get_settings()

    if not filename or "." not in filename:
        raise UploadValidationError("File must have a valid extension.")

    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extensions:
        allowed = ", ".join(settings.allowed_extensions)
        raise UploadValidationError(f"Unsupported file type '{ext}'. Allowed: {allowed}")

    if len(content) == 0:
        raise UploadValidationError("Uploaded file is empty.")

    if len(content) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise UploadValidationError(f"File exceeds the {mb} MB upload limit.")

    # Minimal magic-byte sniffing so a renamed .exe-as-.txt can't sneak past
    # the extension check.
    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise UploadValidationError("File does not look like a valid PDF.")
    if ext == ".docx" and not content.startswith(b"PK\x03\x04"):
        raise UploadValidationError("File does not look like a valid DOCX.")
    if ext == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise UploadValidationError("File does not look like a valid PNG image.")
    if ext in (".jpg", ".jpeg") and not (content.startswith(b"\xff\xd8\xff") or b"JFIF" in content[:20] or b"Exif" in content[:20]):
        raise UploadValidationError("File does not look like a valid JPEG image.")
    if ext == ".webp" and not (content[:4] == b"RIFF" and content[8:12] == b"WEBP"):
        raise UploadValidationError("File does not look like a valid WebP image.")


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "bank_account": re.compile(r"\b(?:acct|account)\s*(?:no\.?|number)?[:#]?\s*\d{6,17}\b", re.IGNORECASE),
    "dob": re.compile(r"\b(?:DOB|Date of birth|Birth date|born on)[:\s]+(?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12]\d|3[01])[-/.](?:19|20)\d{2}\b", re.IGNORECASE),
    "ip_address": re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
    "street_address": re.compile(r"\b\d{1,5}\s+[A-Za-z0-9\.\s]{2,25}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Court|Ct|Lane|Ln|Way)\b", re.IGNORECASE),
}


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace personal identifiers with typed placeholders.

    Returns the redacted text plus counts per category so callers (and audit
    logs) can record *that* redaction happened without ever persisting the
    sensitive values themselves. This runs before any text reaches an LLM
    provider and before any text is logged.
    """
    counts: dict[str, int] = {}
    redacted = text
    for label, pattern in _PII_PATTERNS.items():
        redacted, n = pattern.subn(f"[REDACTED_{label.upper()}]", redacted)
        if n:
            counts[label] = n
    return redacted, counts


# ---------------------------------------------------------------------------
# Encryption at rest
# ---------------------------------------------------------------------------

_dev_fallback_key: bytes | None = None


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key
    if not key:
        # Dev convenience only: main.py refuses to boot in production without
        # an explicit LEASELENS_ENCRYPTION_KEY. We still need a *stable* key
        # for the lifetime of the process here (generating a fresh key per
        # call would make every previously-encrypted document undecryptable),
        # so it's generated once and cached -- never persisted, and lost on
        # restart, which is exactly why production must set a real key.
        global _dev_fallback_key
        if _dev_fallback_key is None:
            _dev_fallback_key = Fernet.generate_key()
        key = _dev_fallback_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_text(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_text(token: bytes) -> str:
    return _get_fernet().decrypt(token).decode("utf-8")


# ---------------------------------------------------------------------------
# Rate limiting (pluggable: in-memory sliding window by default; Redis if
# LEASELENS_REDIS_URL is configured for multi-worker production deployments).
# ---------------------------------------------------------------------------

@dataclass
class RateLimiter:
    max_requests: int
    window_seconds: int

    def __post_init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True


class RedisRateLimiter:
    """Distributed token-bucket rate limiter backed by Redis."""

    def __init__(self, redis_client, max_requests: int, window_seconds: int) -> None:
        self.client = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def allow(self, key: str) -> bool:
        try:
            rkey = f"ratelimit:{key}"
            pipe = self.client.pipeline()
            now = time.time()
            cutoff = now - self.window_seconds
            pipe.zremrangebyscore(rkey, 0, cutoff)
            pipe.zadd(rkey, {str(now): now})
            pipe.zcard(rkey)
            pipe.expire(rkey, self.window_seconds + 5)
            _, _, count, _ = pipe.execute()
            return count <= self.max_requests
        except Exception:
            return True  # Fail open on Redis connectivity issue to avoid service outage


_limiter: RateLimiter | RedisRateLimiter | None = None


def get_rate_limiter() -> RateLimiter | RedisRateLimiter:
    global _limiter
    if _limiter is None:
        settings = get_settings()
        if settings.redis_url:
            try:
                import redis
                client = redis.from_url(settings.redis_url)
                _limiter = RedisRateLimiter(client, settings.rate_limit_requests, settings.rate_limit_window_seconds)
                return _limiter
            except Exception:
                pass
        _limiter = RateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
    return _limiter


PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+instructions\b"),
    re.compile(r"(?i)\bsystem\s+prompt\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(DAN|unfiltered|jailbroken)\b"),
    re.compile(r"(?i)\bdisregard\s+(the\s+)?(rules|instructions)\b"),
]


def sanitize_user_input(text: str) -> str:
    """Sanitize user input against prompt injection attacks and XSS script tags."""
    if not text:
        return ""
    text = re.sub(r"(?i)<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", text)
    for pattern in PROMPT_INJECTION_PATTERNS:
        text = pattern.sub("[REDACTED_INJECTION]", text)
    return text.strip()

