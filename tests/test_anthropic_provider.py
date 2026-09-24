"""
Tests the Anthropic provider's request/response handling WITHOUT making any
real network call -- httpx.post is monkeypatched. This keeps CI free, fast,
and deterministic while still exercising the JSON-parsing and schema-mapping
logic that talks to the real API in production.
"""
from __future__ import annotations

import json

import pytest

from app.classification import DocumentType
from app.rubric import get_rubric


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _fake_message(json_body: dict) -> _FakeResponse:
    return _FakeResponse({"content": [{"type": "text", "text": json.dumps(json_body)}]})


@pytest.fixture
def anthropic_provider(monkeypatch):
    monkeypatch.setenv("LEASELENS_ANTHROPIC_API_KEY", "fake-key-for-tests")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.llm.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider()
    get_settings.cache_clear()
    return provider


def test_extract_clauses_maps_json_response(monkeypatch, anthropic_provider, sample_lease_text):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")

    fake_body = {
        "findings": [
            {
                "rule_id": "security_deposit_terms",
                "present": True,
                "severity": "info",
                "excerpt": "security deposit of $2,400",
                "explanation": "Deposit terms are stated.",
            }
        ]
    }

    def fake_post(url, headers, json, timeout):  # noqa: A002
        return _fake_message(fake_body)

    monkeypatch.setattr("httpx.post", fake_post)

    findings = anthropic_provider.extract_clauses(sample_lease_text, rubric)
    assert len(findings) == 1
    assert findings[0].rule_id == "security_deposit_terms"
    assert findings[0].present is True
    assert findings[0].title == "Security deposit amount & return terms"


def test_answer_question_maps_json_response(monkeypatch, anthropic_provider):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    fake_body = {
        "answer": "The deposit is $2,400.",
        "grounded": True,
        "citations": ["security deposit of $2,400"],
        "seeks_advice": False,
    }

    monkeypatch.setattr("httpx.post", lambda *a, **k: _fake_message(fake_body))

    result = anthropic_provider.answer_question("how much is the deposit", ["deposit clause text"], rubric)
    assert result.grounded is True
    assert result.disclaimer is None
    assert "2,400" in result.answer


def test_answer_question_advice_seeking_gets_disclaimer(monkeypatch, anthropic_provider):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    fake_body = {"answer": "Not specified.", "grounded": False, "citations": [], "seeks_advice": True}
    monkeypatch.setattr("httpx.post", lambda *a, **k: _fake_message(fake_body))

    result = anthropic_provider.answer_question("is this legal", ["some text"], rubric)
    assert result.disclaimer is not None
    assert "not legal advice" in result.disclaimer.lower()


def test_plain_language_summary_maps_json_response(monkeypatch, anthropic_provider, sample_lease_text):
    fake_body = {"summary": "This lease covers rent, deposit, and entry notice terms."}
    monkeypatch.setattr("httpx.post", lambda *a, **k: _fake_message(fake_body))

    summary = anthropic_provider.plain_language_summary(sample_lease_text, [])
    assert "rent" in summary.lower()


def test_strips_markdown_code_fences_from_response(monkeypatch, anthropic_provider):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    fenced_text = "```json\n" + json.dumps({"answer": "ok", "grounded": True, "citations": [], "seeks_advice": False}) + "\n```"
    fake_response = _FakeResponse({"content": [{"type": "text", "text": fenced_text}]})
    monkeypatch.setattr("httpx.post", lambda *a, **k: fake_response)

    result = anthropic_provider.answer_question("q", ["c"], rubric)
    assert result.answer == "ok"


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("LEASELENS_ANTHROPIC_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.llm.anthropic_provider import AnthropicProvider

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()
    get_settings.cache_clear()
