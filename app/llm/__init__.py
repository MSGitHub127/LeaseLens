from app.config import get_settings
from app.llm.mock_provider import MockProvider
from app.llm.provider import LLMProvider

_cached_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Factory that returns the configured provider, cached for reuse.

    Defaults to MockProvider so the app runs fully offline out of the box.
    Anthropic's SDK/HTTP client is only imported when explicitly selected,
    keeping the mock/test path free of any network dependency.
    """
    global _cached_provider
    if _cached_provider is not None:
        return _cached_provider

    settings = get_settings()
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        _cached_provider = AnthropicProvider()
    else:
        _cached_provider = MockProvider()
    return _cached_provider


def reset_provider_cache() -> None:
    """Test helper: allow tests to swap providers between cases."""
    global _cached_provider
    _cached_provider = None
