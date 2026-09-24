from __future__ import annotations

from app.llm import get_llm_provider
from app.llm.provider import QAAnswer
from app.parsing import chunk_text
from app.rag import retrieve_relevant_chunks
from app.rubric import Rubric


def answer_question(document_text: str, question: str, rubric: Rubric) -> QAAnswer:
    """Grounded Q&A: retrieve only the chunks relevant to the question, then
    ask the provider to answer strictly from them. This keeps answers scoped
    to what the document actually says (see provider contract in
    app/llm/provider.py) instead of the model free-associating about tenancy
    law in general.
    """
    if not question.strip():
        return QAAnswer(answer="Please ask a specific question about the document.", grounded=False, citations=[], disclaimer=None)

    chunks = chunk_text(document_text)
    relevant = retrieve_relevant_chunks(question, chunks, top_k=4)

    provider = get_llm_provider()
    return provider.answer_question(question, relevant, rubric)
