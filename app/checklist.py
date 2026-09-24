from __future__ import annotations

from app.extraction import AnalysisResult
from app.models import ChecklistItemOut

_PRIORITY_BY_SEVERITY = {
    "high": "ask_before_signing",
    "medium": "confirm_in_writing",
    "low": "good_to_know",
    "info": "good_to_know",
}

_ORDER = {"ask_before_signing": 0, "confirm_in_writing": 1, "good_to_know": 2}


def generate_checklist(analysis: AnalysisResult) -> list[ChecklistItemOut]:
    """Turn findings into an action list a renter can actually use -- either
    to raise with the landlord before signing, or to bring to a lawyer/tenant
    rights clinic as prepared questions.
    """
    items: list[ChecklistItemOut] = []
    for finding in analysis.findings:
        if finding.present:
            continue  # only missing/ambiguous items need action
        priority = _PRIORITY_BY_SEVERITY.get(finding.severity, "good_to_know")
        items.append(ChecklistItemOut(priority=priority, text=f"{finding.title}: {finding.explanation}"))

    # Always include a generic "prepare for a professional" item so the
    # checklist never implies the tool is a substitute for one.
    items.append(
        ChecklistItemOut(
            priority="good_to_know",
            text="Bring this checklist and the original document to a tenant rights clinic or "
                 "attorney if any 'ask before signing' item isn't resolved to your satisfaction.",
        )
    )

    items.sort(key=lambda item: _ORDER.get(item.priority, 99))
    return items


def generate_consultation_brief(analysis: AnalysisResult, filename: str = "Tenancy Document") -> str:
    """Produce a formatted Markdown brief designed for a tenant to bring to a
    tenant rights clinic, legal aid organization, or housing attorney.
    """
    doc_type = analysis.classification.document_type.value.replace("_", " ").title()
    jurisdiction = analysis.classification.jurisdiction or "General / Multi-State"
    score = analysis.tenant_protection_score

    sections = [
        "# Legal Consultation Brief & Tenant Advocacy Packet",
        "**Prepared by LeaseLens** | *Confidential Tenant Intake Document*",
        "",
        "## 1. Document Overview",
        f"- **File / Context:** {filename}",
        f"- **Document Type:** {doc_type} (Confidence: {round(analysis.classification.type_confidence * 100)}%)",
        f"- **Jurisdiction:** {jurisdiction}",
        f"- **Tenant Protection Score:** {score} / 100",
        "",
        "## 2. Plain-Language Summary",
        analysis.plain_language_summary,
        "",
        "## 3. Protection Category Breakdown",
    ]

    for cat, cat_score in analysis.category_scores.items():
        sections.append(f"- **{cat.replace('_', ' ').title()}:** {cat_score}% protection coverage")

    sections.extend(["", "## 4. Critical Missing Protections & Red Flags (Ask Before Signing)"])
    high_risks = [f for f in analysis.findings if not f.present and f.severity == "high"]
    if high_risks:
        for f in high_risks:
            sections.append(f"- **{f.title}:** {f.explanation}")
    else:
        sections.append("- *No high-severity missing protections detected.*")

    sections.extend(["", "## 5. Items to Confirm in Writing"])
    med_risks = [f for f in analysis.findings if not f.present and f.severity == "medium"]
    if med_risks:
        for f in med_risks:
            sections.append(f"- **{f.title}:** {f.explanation}")
    else:
        sections.append("- *No medium-severity ambiguities detected.*")

    sections.extend([
        "",
        "## 6. Recommended Questions for Legal Professional / Tenant Clinic",
        "1. Does state or municipal tenant protection law imply any mandatory warranty of habitability terms that this document omitted?",
        "2. Are the specific dispute resolution, fee structures, or notice windows listed legally enforceable in this jurisdiction?",
        "3. If any early termination or sublease restriction applies, what are the tenant's statutory rights to mitigate damages?",
        "",
        "## 7. Important Disclaimer",
        "This packet provides document organization and informational analysis, not formal legal advice. "
        "Tenancy laws, municipal rent boards, and court precedents vary by local city/county jurisdiction. "
        "Consult a licensed attorney or certified tenant rights advocacy organization for formal representation.",
    ])

    return "\n".join(sections)
