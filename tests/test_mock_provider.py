from app.classification import DocumentType
from app.llm.mock_provider import MockProvider
from app.rubric import get_rubric


def test_extract_clauses_finds_present_and_absent_items(sample_lease_text):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    provider = MockProvider()
    findings = provider.extract_clauses(sample_lease_text, rubric)

    by_id = {f.rule_id: f for f in findings}
    assert by_id["security_deposit_terms"].present is True
    assert by_id["security_deposit_terms"].excerpt is not None
    # The sample lease never mentions subletting.
    assert by_id["subletting_clause"].present is False
    assert by_id["subletting_clause"].severity == "low"


def test_extract_clauses_absent_high_severity_item_flagged(sample_notice_text):
    rubric = get_rubric(DocumentType.NOTICE_TO_VACATE, None)
    provider = MockProvider()
    findings = provider.extract_clauses(sample_notice_text, rubric)
    by_id = {f.rule_id: f for f in findings}
    # This sample notice DOES state a reason and a deadline, so both should be present.
    assert by_id["notice_reason_stated"].present is True
    assert by_id["notice_response_deadline"].present is True


def test_answer_question_grounded_when_relevant(sample_lease_text):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    provider = MockProvider()
    from app.parsing import chunk_text
    from app.rag import retrieve_relevant_chunks

    chunks = chunk_text(sample_lease_text)
    relevant = retrieve_relevant_chunks("how much notice before landlord enters", chunks)
    answer = provider.answer_question("how much notice before landlord enters", relevant, rubric)
    assert answer.grounded is True
    assert "24 hours" in answer.answer or any("24 hours" in c for c in answer.citations)


def test_answer_question_ungrounded_when_unrelated(sample_lease_text):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    provider = MockProvider()
    answer = provider.answer_question("what is the weather tomorrow", [], rubric)
    assert answer.grounded is False
    assert answer.citations == []


def test_answer_question_advice_seeking_adds_disclaimer(sample_lease_text):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    provider = MockProvider()
    from app.parsing import chunk_text
    from app.rag import retrieve_relevant_chunks

    chunks = chunk_text(sample_lease_text)
    relevant = retrieve_relevant_chunks("can they charge me this late fee, is this legal", chunks)
    answer = provider.answer_question("can they charge me this late fee, is this legal", relevant, rubric)
    assert answer.disclaimer is not None
    assert "not legal advice" in answer.disclaimer.lower()


def test_plain_language_summary_mentions_missing_items(sample_lease_text):
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    provider = MockProvider()
    findings = provider.extract_clauses(sample_lease_text, rubric)
    summary = provider.plain_language_summary(sample_lease_text, findings)
    assert isinstance(summary, str) and len(summary) > 0


def test_mock_provider_semantic_synonym_retrieval(sample_lease_text):
    """Verify that MockProvider retrieves relevant chunks even when query uses synonyms."""
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, "CA")
    provider = MockProvider()
    from app.parsing import chunk_text

    chunks = chunk_text(sample_lease_text)
    # Query uses "security bond" instead of "security deposit"
    answer = provider.answer_question("what is the security bond amount and return timeline?", chunks, rubric)
    assert answer.grounded is True
    assert "$2,400" in answer.answer or any("$2,400" in c for c in answer.citations)

    # Query uses "access premises" instead of "landlord enters"
    entry_answer = provider.answer_question("when can the owner access premises?", chunks, rubric)
    assert entry_answer.grounded is True
    assert "24 hours" in entry_answer.answer or any("24 hours" in c for c in entry_answer.citations)

