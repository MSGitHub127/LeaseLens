from app.classification import DocumentType
from app.rubric import get_rubric


def test_lease_rubric_differs_from_notice_rubric():
    """This is the crux test for 'context-aware decision making': the same
    engine must produce materially different rule sets for different
    document types.
    """
    lease_rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, jurisdiction=None)
    notice_rubric = get_rubric(DocumentType.NOTICE_TO_VACATE, jurisdiction=None)

    lease_ids = {r.id for r in lease_rubric.rules}
    notice_ids = {r.id for r in notice_rubric.rules}

    assert lease_ids != notice_ids
    assert "security_deposit_terms" in lease_ids
    assert "notice_response_deadline" in notice_ids
    assert "notice_response_deadline" not in lease_ids


def test_sublease_rubric_includes_sublease_specific_rules():
    rubric = get_rubric(DocumentType.SUBLEASE, jurisdiction=None)
    ids = {r.id for r in rubric.rules}
    assert "landlord_consent" in ids
    assert "original_lease_incorporated" in ids


def test_jurisdiction_attaches_state_parameters():
    ca_rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, jurisdiction="CA")
    tx_rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, jurisdiction="TX")

    assert ca_rubric.state_parameters["deposit_cap_months"] == 2
    assert tx_rubric.state_parameters["deposit_cap_months"] is None


def test_unknown_jurisdiction_returns_empty_parameters():
    rubric = get_rubric(DocumentType.RESIDENTIAL_LEASE, jurisdiction="ZZ")
    assert rubric.state_parameters == {}


def test_unknown_document_type_falls_back_to_lease_baseline():
    rubric = get_rubric(DocumentType.UNKNOWN, jurisdiction=None)
    assert len(rubric.rules) > 0
    ids = {r.id for r in rubric.rules}
    assert "security_deposit_terms" in ids
