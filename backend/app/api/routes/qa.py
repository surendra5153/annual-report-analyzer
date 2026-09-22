from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.db.models import Filing, KPI, ProcessingStatus
from app.api.schemas import QARequest, QAResponse, CitationOut
from app.engines.rag_qa import answer_question

router = APIRouter(prefix="/qa", tags=["qa"])


class ConversationTurn(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class QARequestV2(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    filing_ids: List[str] = Field(..., min_length=1)
    conversation_history: Optional[List[ConversationTurn]] = None


class QAResponseV2(QAResponse):
    suggested_questions: List[str] = []


@router.post("/", response_model=QAResponseV2)
def ask_question(payload: QARequestV2, db: Session = Depends(get_db)):
    # Validate all filings exist and are completed
    for fid in payload.filing_ids:
        filing = db.query(Filing).filter(Filing.id == fid).first()
        if not filing:
            raise HTTPException(status_code=404, detail=f"Filing {fid} not found")
        if filing.status != ProcessingStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Filing {fid} is not yet processed (status: {filing.status})"
            )

    # Build KPI lookup for verification (verified KPIs only)
    kpis = db.query(KPI).filter(
        KPI.filing_id.in_(payload.filing_ids),
        KPI.is_verified == True,  # noqa: E712
    ).all()
    kpi_lookup = {k.name: k.value for k in kpis if k.value is not None}

    # Convert conversation history
    history = None
    if payload.conversation_history:
        history = [{"role": t.role, "content": t.content} for t in payload.conversation_history]

    result = answer_question(
        question=payload.question,
        filing_ids=payload.filing_ids,
        kpi_lookup=kpi_lookup,
        conversation_history=history,
    )

    return QAResponseV2(
        question=result.question,
        answer=result.answer,
        citations=[
            CitationOut(
                page_number=c.page_number,
                excerpt=c.excerpt,
                filing_id=c.filing_id,
            )
            for c in result.citations
        ],
        confidence=result.confidence,
        verified_against_kpi=result.verified_against_kpi,
        kpi_verification_note=result.kpi_verification_note,
        suggested_questions=result.suggested_questions,
    )
