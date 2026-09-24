from __future__ import annotations

from app.extraction import AnalysisResult
from app.models import CompareRuleDiffOut


def compare_analyses(analysis_a: AnalysisResult, analysis_b: AnalysisResult) -> tuple[list[CompareRuleDiffOut], str]:
    """Align two documents' findings by rule id and report where their
    coverage of the same protections/obligations differs. If the two
    documents were classified differently (e.g. a lease vs. an addendum),
    only rules evaluated on both sides are compared, and that's noted.
    """
    by_id_a = {f.rule_id: f for f in analysis_a.findings}
    by_id_b = {f.rule_id: f for f in analysis_b.findings}
    shared_ids = [rid for rid in by_id_a if rid in by_id_b]

    diffs: list[CompareRuleDiffOut] = []
    changed_count = 0
    for rid in shared_ids:
        fa, fb = by_id_a[rid], by_id_b[rid]
        status_a = "present" if fa.present else "absent"
        status_b = "present" if fb.present else "absent"
        changed = status_a != status_b
        if changed:
            changed_count += 1
        diffs.append(CompareRuleDiffOut(rule_id=rid, title=fa.title, status_a=status_a, status_b=status_b, changed=changed))

    if not shared_ids:
        summary = "These documents were classified differently enough that there's no shared checklist to compare directly."
    elif changed_count == 0:
        summary = f"Both documents address the same {len(shared_ids)} checked items -- no coverage differences found."
    else:
        summary = f"{changed_count} of {len(shared_ids)} checked items differ between the two documents."

    return diffs, summary
