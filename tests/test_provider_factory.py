from app.llm import get_llm_provider, reset_provider_cache
from app.llm.mock_provider import MockProvider


def test_defaults_to_mock_provider(monkeypatch):
    monkeypatch.setenv("LEASELENS_LLM_PROVIDER", "mock")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_provider_cache()
    provider = get_llm_provider()
    assert isinstance(provider, MockProvider)
    get_settings.cache_clear()
    reset_provider_cache()


def test_selects_anthropic_provider_when_configured_and_key_present(monkeypatch):
    monkeypatch.setenv("LEASELENS_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LEASELENS_ANTHROPIC_API_KEY", "fake-key")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_provider_cache()
    from app.llm.anthropic_provider import AnthropicProvider

    provider = get_llm_provider()
    assert isinstance(provider, AnthropicProvider)

    get_settings.cache_clear()
    reset_provider_cache()


def test_provider_is_cached_across_calls(monkeypatch):
    monkeypatch.setenv("LEASELENS_LLM_PROVIDER", "mock")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_provider_cache()
    first = get_llm_provider()
    second = get_llm_provider()
    assert first is second
    get_settings.cache_clear()
    reset_provider_cache()
