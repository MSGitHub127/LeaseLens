from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_session
from app.checklist import generate_checklist, generate_consultation_brief
from app.compare import compare_analyses
from app.db import get_db
from app.deps import enforce_rate_limit
from app.extraction import AnalysisResult, analyze_document
from app.models import (
    AnalysisOut,
    ChecklistOut,
    ClauseFindingOut,
    CompareOut,
    CompareRequestIn,
    CompareRuleDiffOut,
    ConsultationBriefOut,
)
from app.routers.documents import _get_owned_document
from app.security import decrypt_text

router = APIRouter(prefix="/api", tags=["analysis"])


def _load_analysis(db: Session, document_id: str, session_id: str) -> tuple[AnalysisResult, str]:
    record = _get_owned_document(db, document_id, session_id)
    text = decrypt_text(record.encrypted_text)
    return analyze_document(text), record.filename


@router.post("/documents/{document_id}/analyze", response_model=AnalysisOut)
def analyze(
    document_id: str,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
    _: None = Depends(enforce_rate_limit),
) -> AnalysisOut:
    analysis, _ = _load_analysis(db, document_id, session_id)
    findings_out = [
        ClauseFindingOut(
            rule_id=f.rule_id, title=f.title, present=f.present, severity=f.severity,
            excerpt=f.excerpt, explanation=f.explanation,
        )
        for f in analysis.findings
    ]
    return AnalysisOut(
        document_id=document_id,
        document_type=analysis.classification.document_type.value,
        document_type_confidence=analysis.classification.type_confidence,
        jurisdiction=analysis.classification.jurisdiction,
        jurisdiction_confidence=analysis.classification.jurisdiction_confidence,
        findings=findings_out,
        plain_language_summary=analysis.plain_language_summary,
        high_risk_count=analysis.high_risk_count,
        medium_risk_count=analysis.medium_risk_count,
        tenant_protection_score=analysis.tenant_protection_score,
        category_scores=analysis.category_scores,
    )


@router.get("/documents/{document_id}/checklist", response_model=ChecklistOut)
def checklist(
    document_id: str,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> ChecklistOut:
    analysis, _ = _load_analysis(db, document_id, session_id)
    items = generate_checklist(analysis)
    return ChecklistOut(document_id=document_id, items=items)


@router.get("/documents/{document_id}/export-brief", response_model=ConsultationBriefOut)
def export_brief(
    document_id: str,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> ConsultationBriefOut:
    analysis, filename = _load_analysis(db, document_id, session_id)
    brief_md = generate_consultation_brief(analysis, filename=filename)
    return ConsultationBriefOut(
        document_id=document_id,
        document_type=analysis.classification.document_type.value,
        jurisdiction=analysis.classification.jurisdiction,
        tenant_protection_score=analysis.tenant_protection_score,
        brief_markdown=brief_md,
    )


@router.post("/documents/compare", response_model=CompareOut)
def compare(
    body: CompareRequestIn,
    session_id: str = Depends(get_current_session),
    db: Session = Depends(get_db),
    _: None = Depends(enforce_rate_limit),
) -> CompareOut:
    analysis_a, _ = _load_analysis(db, body.document_id_a, session_id)
    analysis_b, _ = _load_analysis(db, body.document_id_b, session_id)
    diffs, summary = compare_analyses(analysis_a, analysis_b)
    return CompareOut(
        document_id_a=body.document_id_a,
        document_id_b=body.document_id_b,
        diffs=[CompareRuleDiffOut(**d.model_dump()) for d in diffs],
        summary=summary,
    )
