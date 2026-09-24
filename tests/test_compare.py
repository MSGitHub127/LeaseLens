from app.compare import compare_analyses
from app.extraction import analyze_document


def test_compare_identical_documents_reports_no_changes(sample_lease_text):
    a = analyze_document(sample_lease_text)
    b = analyze_document(sample_lease_text)
    diffs, summary = compare_analyses(a, b)
    assert all(not d.changed for d in diffs)
    assert "no coverage differences" in summary.lower()


def test_compare_detects_a_missing_clause():
    lease_with_entry_clause = """
    RESIDENTIAL LEASE AGREEMENT between Landlord and Tenant in California.
    Landlord shall provide at least 24 hours notice to enter the premises.
    Tenant shall pay a security deposit of $1,000.
    """
    lease_without_entry_clause = """
    RESIDENTIAL LEASE AGREEMENT between Landlord and Tenant in California.
    Tenant shall pay a security deposit of $1,000.
    """
    a = analyze_document(lease_with_entry_clause)
    b = analyze_document(lease_without_entry_clause)
    diffs, summary = compare_analyses(a, b)

    entry_diff = next(d for d in diffs if d.rule_id == "entry_notice")
    assert entry_diff.status_a == "present"
    assert entry_diff.status_b == "absent"
    assert entry_diff.changed is True
    assert "differ" in summary.lower()


def test_compare_documents_with_no_shared_rules(sample_lease_text, sample_notice_text):
    a = analyze_document(sample_lease_text)
    b = analyze_document(sample_notice_text)
    diffs, summary = compare_analyses(a, b)
    assert diffs == []
    assert "no shared checklist" in summary.lower()
