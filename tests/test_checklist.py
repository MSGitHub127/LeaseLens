from app.checklist import generate_checklist
from app.extraction import analyze_document


def test_checklist_prioritizes_high_severity_missing_items(sample_lease_text):
    analysis = analyze_document(sample_lease_text)
    items = generate_checklist(analysis)

    priorities_in_order = [item.priority for item in items]
    # "ask_before_signing" (high severity) items, if any, must precede
    # "confirm_in_writing" (medium), which must precede "good_to_know".
    order_rank = {"ask_before_signing": 0, "confirm_in_writing": 1, "good_to_know": 2}
    ranks = [order_rank[p] for p in priorities_in_order]
    assert ranks == sorted(ranks)


def test_checklist_always_includes_professional_referral(sample_lease_text):
    analysis = analyze_document(sample_lease_text)
    items = generate_checklist(analysis)
    assert any("tenant rights clinic" in item.text.lower() or "attorney" in item.text.lower() for item in items)


def test_checklist_excludes_items_the_document_already_covers(sample_lease_text):
    analysis = analyze_document(sample_lease_text)
    items = generate_checklist(analysis)
    present_titles = {f.title for f in analysis.findings if f.present}
    for item in items:
        # No checklist item should be generated purely for something already present.
        assert not any(item.text.startswith(title) for title in present_titles)
