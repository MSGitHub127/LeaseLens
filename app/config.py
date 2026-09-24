"""
Centralized configuration. All tunables come from environment variables so the
same image can move from local dev -> CI -> production without code changes.
Never hardcode secrets here; .env.example documents what must be supplied.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LEASELENS_", extra="ignore")

    # --- Identity / environment ---
    app_name: str = "LeaseLens API"
    environment: str = "development"  # development | staging | production
    database_url: str = "sqlite:///./leaselens.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    # --- Security ---
    # 32+ byte random secret used to sign session tokens. MUST be overridden
    # in any non-development environment (enforced in main.py on startup).
    secret_key: str = "dev-only-insecure-secret-change-me"
    token_expire_minutes: int = 60
    encryption_key: str = ""  # Fernet key for document-at-rest encryption; generated if blank in dev
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # --- Upload limits (defense against resource-exhaustion / zip-bomb style abuse) ---
    max_upload_bytes: int = 16 * 1024 * 1024  # 16 MB (supports high-res phone photos & multi-page PDFs)
    allowed_extensions: tuple[str, ...] = (".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp")

    # --- Rate limiting (in-memory token bucket; or Redis for multi-instance prod) ---
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    redis_url: str = ""  # optional redis:// URL for distributed rate limiting

    # --- Data retention (privacy-by-design: don't keep sensitive docs forever) ---
    document_retention_days: int = 30

    # --- LLM provider ---
    # "mock" runs fully offline with deterministic rule-based logic (used in
    # tests/CI and as a safe default). "anthropic" calls the real API and
    # requires LEASELENS_ANTHROPIC_API_KEY.
    llm_provider: str = "mock"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    return Settings()
