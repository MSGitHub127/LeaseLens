"""
The rubric engine is where "logical decision-making based on user context"
lives: given a document type + jurisdiction, it decides *which* checks apply
and *what thresholds* they use, before any clause text is examined.

Design note: the per-state figures below (deposit caps, notice periods) are
illustrative examples, not legal research, and are clearly labeled as such
everywhere they surface (API responses, UI, README). A production system
would source these from a maintained legal database and cite it -- the point
here is the *architecture* for context-driven rule selection, not a claim of
legal authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.classification import DocumentType

Severity = str  # "high" | "medium" | "low" | "info"


@dataclass(frozen=True)
class RubricRule:
    id: str
    title: str
    category: str  # e.g. "financial", "termination", "maintenance", "access", "legal_compliance"
    keywords: tuple[str, ...]  # any hit => clause considered "present" in the document
    guidance: str  # plain-language explanation shown to the user
    severity_if_absent: Severity  # risk of this protection/clause being missing entirely
    applies_to: tuple[DocumentType, ...] = (DocumentType.RESIDENTIAL_LEASE,)


# Baseline rules that apply to any residential lease regardless of state.
_BASE_LEASE_RULES: tuple[RubricRule, ...] = (
    RubricRule(
        id="security_deposit_terms",
        title="Security deposit amount & return terms",
        category="financial",
        keywords=("security deposit", "damage deposit"),
        guidance="Confirm the deposit amount, the timeline for its return after move-out, and what deductions are allowed.",
        severity_if_absent="high",
    ),
    RubricRule(
        id="rent_due_date_and_late_fees",
        title="Rent due date & late fee terms",
        category="financial",
        keywords=("late fee", "due date", "grace period"),
        guidance="Look for the exact due date, any grace period, and how late fees are calculated -- flat fee vs. daily accrual.",
        severity_if_absent="medium",
    ),
    RubricRule(
        id="maintenance_responsibility",
        title="Maintenance & repair responsibilities",
        category="maintenance",
        keywords=("maintenance", "repair", "habitable", "habitability"),
        guidance="Leases should state who fixes what. Silence here often defaults to landlord-favorable interpretations.",
        severity_if_absent="medium",
    ),
    RubricRule(
        id="entry_notice",
        title="Landlord entry & notice requirements",
        category="access",
        keywords=("right of entry", "notice to enter", "access to the premises"),
        guidance="Most states require advance notice before a landlord enters except in emergencies -- check the notice window stated here.",
        severity_if_absent="medium",
    ),
    RubricRule(
        id="early_termination",
        title="Early termination / lease-break terms",
        category="termination",
        keywords=("early termination", "break the lease", "lease break", "termination fee"),
        guidance="If your plans might change, know the exact penalty for ending the lease early.",
        severity_if_absent="low",
    ),
    RubricRule(
        id="renewal_and_rent_increase",
        title="Renewal terms & rent increase notice",
        category="financial",
        keywords=("renewal", "rent increase", "auto-renew", "automatically renew"),
        guidance="Check whether the lease auto-renews and how much notice you'd get before a rent increase.",
        severity_if_absent="low",
    ),
    RubricRule(
        id="subletting_clause",
        title="Subletting / assignment rights",
        category="flexibility",
        keywords=("sublet", "sublease", "assign this lease", "assignment"),
        guidance="Know whether you're allowed to sublet if you need to leave before the lease ends.",
        severity_if_absent="low",
    ),
    RubricRule(
        id="waiver_of_rights",
        title="Clauses waiving tenant legal rights",
        category="legal_compliance",
        keywords=("waives", "waiver of", "tenant agrees not to", "hold landlord harmless"),
        guidance="Broad waivers of legal rights (e.g. right to sue, right to habitable premises) are frequently unenforceable "
                 "and worth flagging for a professional -- they're a signal the lease needs closer review.",
        severity_if_absent="info",
    ),
)

_NOTICE_RULES: tuple[RubricRule, ...] = (
    RubricRule(
        id="notice_reason_stated",
        title="Reason for the notice",
        category="legal_compliance",
        keywords=("for cause", "non-payment", "lease violation", "no-fault", "reason for termination"),
        guidance="Notices with-cause and no-cause follow different rules and different response timelines -- confirm which this is.",
        severity_if_absent="high",
        applies_to=(DocumentType.NOTICE_TO_VACATE,),
    ),
    RubricRule(
        id="notice_response_deadline",
        title="Deadline to respond or cure",
        category="termination",
        keywords=("days to cure", "days to vacate", "by the date", "deadline"),
        guidance="Missing this deadline can waive your ability to contest the notice -- confirm the exact date.",
        severity_if_absent="high",
        applies_to=(DocumentType.NOTICE_TO_VACATE,),
    ),
)

_SUBLEASE_RULES: tuple[RubricRule, ...] = (
    RubricRule(
        id="original_lease_incorporated",
        title="Original lease terms incorporated by reference",
        category="legal_compliance",
        keywords=("original lease", "master lease", "incorporated by reference"),
        guidance="A sublease should reference and stay consistent with the original lease -- ask to see that document too.",
        severity_if_absent="medium",
        applies_to=(DocumentType.SUBLEASE,),
    ),
    RubricRule(
        id="landlord_consent",
        title="Landlord's written consent to sublet",
        category="legal_compliance",
        keywords=("landlord consent", "written consent", "approved by landlord"),
        guidance="Subletting without the landlord's required consent can be treated as a lease violation by the original tenant.",
        severity_if_absent="high",
        applies_to=(DocumentType.SUBLEASE,),
    ),
)

# State-specific parameter overrides. Illustrative examples only -- see module
# docstring. `notice_days` = advance notice typically required before entry;
# `deposit_cap_months` = a commonly-cited multiple of monthly rent.
STATE_PARAMETERS: dict[str, dict] = {
    "CA": {"entry_notice_hours": 24, "deposit_cap_months": 2, "note": "CA law caps deposits and sets a 21-day return window (illustrative -- confirm current statute)."},
    "NY": {"entry_notice_hours": 24, "deposit_cap_months": 1, "note": "NY caps deposits at one month's rent for most tenancies (illustrative)."},
    "TX": {"entry_notice_hours": None, "deposit_cap_months": None, "note": "TX has no statutory deposit cap, but return timelines still apply (illustrative)."},
}


@dataclass
class Rubric:
    document_type: DocumentType
    jurisdiction: str | None
    rules: list[RubricRule]
    state_parameters: dict = field(default_factory=dict)


def get_rubric(document_type: DocumentType, jurisdiction: str | None) -> Rubric:
    """Select and parameterize the checklist for this document's context.

    This is the single decision point: swap the document type or the
    jurisdiction and a materially different rubric comes back.
    """
    pool = _BASE_LEASE_RULES + _NOTICE_RULES + _SUBLEASE_RULES
    applicable = [r for r in pool if document_type in r.applies_to]

    if not applicable:
        # Unknown/unsupported type: fall back to the generic lease baseline
        # so the user still gets useful output rather than an empty result.
        applicable = list(_BASE_LEASE_RULES)

    params = STATE_PARAMETERS.get(jurisdiction or "", {})
    return Rubric(document_type=document_type, jurisdiction=jurisdiction, rules=applicable, state_parameters=params)


def calculate_tenant_protection_score(findings: list, rubric: Rubric) -> tuple[int, dict[str, int]]:
    """Compute a 0-100 Tenant Protection Score based on evaluated rubric rules.

    Weighted by severity:
      - High severity absent: -3 pts weight
      - Medium severity absent: -2 pts weight
      - Low / Info severity: -1 pt weight

    Returns an overall score (0-100) and a category-level percentage breakdown.
    """
    rule_lookup = {r.id: r for r in rubric.rules}
    weights = {"high": 3.0, "medium": 2.0, "low": 1.0, "info": 1.0}

    total_weight = 0.0
    earned_weight = 0.0
    category_totals: dict[str, float] = {}
    category_earned: dict[str, float] = {}

    for f in findings:
        rule = rule_lookup.get(f.rule_id)
        severity = getattr(rule, "severity_if_absent", "medium") if rule else "medium"
        category = getattr(rule, "category", "general") if rule else "general"
        w = weights.get(severity, 1.0)

        total_weight += w
        category_totals[category] = category_totals.get(category, 0.0) + w

        if f.present:
            earned_weight += w
            category_earned[category] = category_earned.get(category, 0.0) + w
        else:
            category_earned.setdefault(category, 0.0)

    overall_score = round((earned_weight / total_weight) * 100) if total_weight > 0 else 100
    category_breakdown = {
        cat: round((category_earned.get(cat, 0.0) / cat_tot) * 100)
        for cat, cat_tot in category_totals.items()
    }
    return overall_score, category_breakdown
