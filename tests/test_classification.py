from app.classification import DocumentType, classify_document


def test_classifies_standard_lease(sample_lease_text):
    result = classify_document(sample_lease_text)
    assert result.document_type == DocumentType.RESIDENTIAL_LEASE
    assert result.type_confidence > 0


def test_classifies_notice_to_vacate(sample_notice_text):
    result = classify_document(sample_notice_text)
    assert result.document_type == DocumentType.NOTICE_TO_VACATE


def test_classifies_sublease(sample_sublease_text):
    result = classify_document(sample_sublease_text)
    assert result.document_type == DocumentType.SUBLEASE


def test_detects_jurisdiction_from_state_name(sample_lease_text):
    result = classify_document(sample_lease_text)
    assert result.jurisdiction == "CA"
    assert result.jurisdiction_confidence > 0


def test_unknown_document_type_for_unrelated_text():
    result = classify_document("This is a grocery list: milk, eggs, bread.")
    assert result.document_type == DocumentType.UNKNOWN


def test_no_jurisdiction_detected_when_absent():
    result = classify_document("This lease agreement is between landlord and tenant.")
    assert result.jurisdiction is None
    assert result.jurisdiction_confidence == 0.0


def test_notice_to_vacate_takes_priority_over_generic_lease_keywords():
    # Contains both "landlord/tenant" (generic lease) AND "notice to vacate"
    # (more specific) -- the more specific classification should win.
    text = "Landlord hereby issues this notice to vacate to Tenant effective immediately."
    result = classify_document(text)
    assert result.document_type == DocumentType.NOTICE_TO_VACATE
