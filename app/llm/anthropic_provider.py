"""
Production LLM provider backed by the Anthropic API. Only imported/used when
LEASELENS_LLM_PROVIDER=anthropic and LEASELENS_ANTHROPIC_API_KEY is set (see
app/llm/__init__.py). Every prompt:

  - Is grounded: the model is given ONLY the document text/chunks and is
    instructed to answer from them alone.
  - Enforces the "not legal advice" boundary in the system prompt, not just
    in post-hoc UI copy.
  - Requests strict JSON output (schema described in-prompt) so responses can
    be validated before ever reaching a user -- no raw model text is trusted.
"""
from __future__ import annotations

import json

import httpx

from app.config import get_settings
from app.llm.provider import ClauseFinding, LLMProvider, QAAnswer
from app.rubric import Rubric

_SYSTEM_PROMPT = (
    "You are LeaseLens, an assistant that helps people understand tenancy documents. "
    "You ONLY use the document text you are given -- never invent clauses, dates, or amounts. "
    "You NEVER give definitive legal advice or tell someone what they are legally entitled to; "
    "you explain what the document says and, where relevant, suggest they confirm specifics "
    "with a tenant rights organization or attorney. If the document does not address something, "
    "say so plainly instead of guessing. Always respond with valid JSON matching the requested schema."
)


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("LEASELENS_ANTHROPIC_API_KEY is required for the anthropic provider.")
        self._api_key = settings.anthropic_api_key
        self._model = settings.anthropic_model

    def extract_clauses(self, document_text: str, rubric: Rubric) -> list[ClauseFinding]:
        rule_specs = [
            {"id": r.id, "title": r.title, "keywords": list(r.keywords), "guidance": r.guidance}
            for r in rubric.rules
        ]
        schema_hint = (
            '{"findings": [{"rule_id": str, "present": bool, "severity": '
            '"high"|"medium"|"low"|"info", "excerpt": str|null, "explanation": str}]}'
        )
        prompt = (
            f"Document type: {rubric.document_type.value}. Jurisdiction: {rubric.jurisdiction or 'unknown'}.\n"
            f"Rules to check:\n{json.dumps(rule_specs, indent=2)}\n\n"
            f"Document text:\n{document_text[:12000]}\n\n"
            f"For each rule, determine if the document addresses it. Return ONLY JSON matching: {schema_hint}"
        )
        data = self._call(prompt)
        findings = []
        for item in data.get("findings", []):
            findings.append(
                ClauseFinding(
                    rule_id=item["rule_id"],
                    title=next((r.title for r in rubric.rules if r.id == item["rule_id"]), item["rule_id"]),
                    present=item.get("present", False),
                    severity=item.get("severity", "info"),
                    excerpt=item.get("excerpt"),
                    explanation=item.get("explanation", ""),
                )
            )
        return findings

    def answer_question(self, question: str, context_chunks: list[str], rubric: Rubric) -> QAAnswer:
        schema_hint = '{"answer": str, "grounded": bool, "citations": [str], "seeks_advice": bool}'
        prompt = (
            f"Question: {question}\n\n"
            f"Relevant document excerpts:\n" + "\n---\n".join(context_chunks[:5]) + "\n\n"
            f"Answer using ONLY these excerpts. If they don't cover it, set grounded=false and say so. "
            f"Return ONLY JSON matching: {schema_hint}"
        )
        data = self._call(prompt)
        disclaimer = None
        if data.get("seeks_advice"):
            disclaimer = (
                "This is general information based on your document, not legal advice. "
                "For guidance specific to your situation, consider a tenant rights clinic or a licensed attorney."
            )
        return QAAnswer(
            answer=data.get("answer", ""),
            grounded=data.get("grounded", False),
            citations=data.get("citations", []),
            disclaimer=disclaimer,
        )

    def plain_language_summary(self, document_text: str, findings: list[ClauseFinding]) -> str:
        prompt = (
            "Summarize this tenancy document in 3-4 plain-language sentences at roughly an 8th-grade "
            "reading level. Do not give legal advice, just describe what the document says.\n\n"
            f"Document text:\n{document_text[:8000]}\n\n"
            'Return ONLY JSON matching: {"summary": str}'
        )
        data = self._call(prompt)
        return data.get("summary", "")

    def extract_text_from_image(self, image_bytes: bytes, mime_type: str) -> str:
        import base64

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._model,
                "max_tokens": 2500,
                "system": _SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Transcribe all text from this tenancy document or notice verbatim. "
                                    "Preserve all clause headings, amounts, dates, and terms accurately. "
                                    "Do not give legal advice; return only the extracted text."
                                ),
                            },
                        ],
                    }
                ],
            },
            timeout=45.0,
        )
        response.raise_for_status()
        payload = response.json()
        return "".join(
            block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"
        ).strip()

    def _call(self, user_prompt: str) -> dict:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._model,
                "max_tokens": 1500,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(text)
