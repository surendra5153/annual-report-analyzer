import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.core.config import settings
from app.db.models import Filing, KPI, ProcessingStatus
from app.services.qa_context import filing_labels, kpi_facts
from app.api.schemas import QARequest, QAResponse, CitationOut
from app.engines.rag_qa import answer_question, stream_answer

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


def _validate_filings(filing_ids: List[str], db: Session) -> Dict[str, str]:
    """Raise 404/400 unless every filing exists and has finished processing; return prompt labels."""
    for fid in filing_ids:
        filing = db.query(Filing).filter(Filing.id == fid).first()
        if not filing:
            raise HTTPException(status_code=404, detail=f"Filing {fid} not found")
        if filing.status != ProcessingStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Filing {fid} is not yet processed (status: {filing.status})"
            )
    return filing_labels(db, filing_ids)


def _facts(filing_ids: List[str], db: Session) -> Optional[List[dict]]:
    return kpi_facts(db, filing_ids) if settings.qa_use_kpi_facts else None


def _history(payload: QARequestV2) -> Optional[List[dict]]:
    if not payload.conversation_history:
        return None
    return [{"role": t.role, "content": t.content} for t in payload.conversation_history]


@router.post("/", response_model=QAResponseV2)
def ask_question(payload: QARequestV2, db: Session = Depends(get_db)):
    labels = _validate_filings(payload.filing_ids, db)

    # Build KPI lookup for verification (verified KPIs only)
    kpis = db.query(KPI).filter(
        KPI.filing_id.in_(payload.filing_ids),
        KPI.is_verified == True,  # noqa: E712
    ).all()
    # Answers quote figures as printed in the report → compare against the raw (pre-normalisation) value
    kpi_lookup = {k.name: (k.raw_value if k.raw_value is not None else k.value) for k in kpis if k.value is not None}

    result = answer_question(
        question=payload.question,
        filing_ids=payload.filing_ids,
        kpi_lookup=kpi_lookup,
        conversation_history=_history(payload),
        filing_labels=labels,
        kpi_facts=_facts(payload.filing_ids, db),
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


@router.post("/stream")
def ask_question_stream(payload: QARequestV2, db: Session = Depends(get_db)):
    """
    Server-Sent Events version of ask_question: emits `sources`, then `token`
    events as the local LLM generates, then `done` (confidence + cited indices).
    """
    labels = _validate_filings(payload.filing_ids, db)
    facts = _facts(payload.filing_ids, db)

    def events():
        try:
            for event in stream_answer(payload.question, payload.filing_ids, _history(payload),
                                       filing_labels=labels, kpi_facts=facts,
                                       statement_pages=settings.qa_statement_pages, model=settings.qa_model,
                                       facts_with_statements=settings.qa_facts_with_statements,
                                       table_reader=settings.qa_table_reader):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Streaming QA failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
