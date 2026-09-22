import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Filing, Company, Job, KPI, Risk, FootnoteFlag, ReportSection, ProcessingStatus
from app.api.schemas import (
    FilingOut, KPIOut, RiskOut, FootnoteFlagOut, SectionOut, DashboardOut, DetectResponse, JobOut
)
from app.core.config import settings

router = APIRouter(prefix="/filings", tags=["filings"])


# ── helpers ────────────────────────────────────────────────────────────────

def _run_pipeline_bg(filing_id: str, prior_filing_id: Optional[str]):
    """Runs the pipeline in a background thread (no Celery needed)."""
    from app.db.database import SessionLocal
    from app.services.pipeline import run_full_pipeline
    db = SessionLocal()
    try:
        run_full_pipeline(filing_id, db, prior_filing_id)
    finally:
        db.close()

def _extract_pdf_text(path: str, max_pages: int = 3) -> str:
    """Return plain text from the first *max_pages* pages of a PDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        pages = min(len(doc), max_pages)
        parts = []
        for i in range(pages):
            parts.append(doc[i].get_text("text"))
        doc.close()
        return "\n".join(parts)[:4000]   # cap at 4k chars for faster LLM call
    except Exception as e:
        return ""


def _detect_metadata_from_text(text: str) -> DetectResponse:
    """Call the LLM to extract filing metadata and validate the PDF."""
    from app.core.llm_client import chat_complete_json
    import re

    # Quick pattern-based detection for common cases (much faster than LLM)
    lowered = text.lower()
    
    # Quick reject non-financial docs
    if not any(kw in lowered for kw in [
        "annual report", "balance sheet", "profit and loss", "income statement",
        "cash flow", "auditor", "fiscal year", "financial statements",
        "chairman", "board of directors", "financial position"
    ]):
        return DetectResponse(
            is_financial_report=False,
            rejection_reason="Document does not appear to be a financial report",
            confidence="medium",
        )
    
    # Try pattern-based extraction first (instant)
    patterns = {
        "fiscal_year": re.compile(r'\b(?:FY|fiscal year|for the year ended|year ending)\s*[:\-]?\s*(?:20)?(\d{2})(?:\s*[-/]\s*(?:20)?(\d{2}))?', re.IGNORECASE),
        "currency": re.compile(r'\b(INR|USD|EUR|GBP|JPY|CNY|₹|\$|€|£)\b'),
        "unit_scale": re.compile(r'\((?:in\s+)?(crores?|lakhs?|millions?|billions?)\)', re.IGNORECASE),
    }
    
    quick_data = {}
    
    # Extract year - take the ending year
    year_match = patterns["fiscal_year"].search(text[:2000])
    if year_match:
        year_str = year_match.group(2) if year_match.group(2) else year_match.group(1)
        try:
            year = int(year_str)
            quick_data["fiscal_year"] = 2000 + year if year < 100 else year
        except:
            pass
    
    # Extract currency
    currency_match = patterns["currency"].search(text[:1500])
    if currency_match:
        curr_map = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}
        curr = currency_match.group(1)
        quick_data["currency"] = curr_map.get(curr, curr)
    
    # Extract unit scale
    unit_match = patterns["unit_scale"].search(text[:1500])
    if unit_match:
        quick_data["unit_scale"] = unit_match.group(1).lower().rstrip('s')

    system_prompt = (
        "Extract metadata from financial report PDF text. Return JSON only.\n\n"
        "Schema: {is_financial_report: bool, rejection_reason: str|null, "
        "company_name: str|null, ticker: str|null, fiscal_year: int|null, "
        "currency: str|null, unit_scale: str|null, report_type: str|null, confidence: str}\n\n"
        "Rules:\n"
        "- is_financial_report=false if not annual report/10-K/20-F\n"
        "- fiscal_year = year period ENDS (FY 2023-24 → 2024)\n"
        "- unit_scale: crores|lakhs|millions|billions|units\n"
        "- currency: INR, USD, EUR, etc.\n"
        "- confidence: high|medium|low"
    )

    try:
        data = chat_complete_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text[:2500]},  # Limit to 2.5k chars for speed
            ],
            max_tokens=250,
        )
        
        # Merge pattern-based results with LLM results (LLM takes precedence)
        result = {**quick_data, **{k: v for k, v in data.items() if v is not None}}
        
        return DetectResponse(
            is_financial_report=bool(result.get("is_financial_report", True)),
            rejection_reason=result.get("rejection_reason"),
            company_name=result.get("company_name"),
            ticker=result.get("ticker"),
            fiscal_year=result.get("fiscal_year"),
            currency=result.get("currency", "INR"),
            unit_scale=result.get("unit_scale", "crores"),
            report_type=result.get("report_type"),
            confidence=result.get("confidence", "medium"),
        )
    except Exception as e:
        # Fallback to pattern-based if LLM fails
        return DetectResponse(
            is_financial_report=True,
            rejection_reason=None,
            company_name=None,
            ticker=None,
            fiscal_year=quick_data.get("fiscal_year"),
            currency=quick_data.get("currency", "INR"),
            unit_scale=quick_data.get("unit_scale", "crores"),
            report_type="Annual Report",
            confidence="low",
        )


def _get_or_create_company(name: str, ticker: Optional[str], sector: Optional[str], db: Session) -> Company:
    """Look up an existing company by ticker (or name), create if absent."""
    company = None
    if ticker:
        company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company and name:
        company = db.query(Company).filter(Company.name == name).first()
    if not company:
        company = Company(
            name=name or "Unknown Company",
            ticker=ticker.upper() if ticker else None,
            sector=sector,
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


# ── routes ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[FilingOut])
def list_filings(company_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Filing)
    if company_id:
        q = q.filter(Filing.company_id == company_id)
    return q.order_by(Filing.fiscal_year.desc()).all()


@router.post("/detect", response_model=DetectResponse)
async def detect_filing(file: UploadFile = File(...)):
    """
    Upload a PDF and get back detected metadata (company, fiscal year,
    currency, unit scale) without persisting anything.

    Returns is_financial_report=false if the PDF doesn't look like a
    financial report, so the frontend can reject it early.
    """
    if not file.filename.lower().endswith(".pdf"):
        return DetectResponse(
            is_financial_report=False,
            rejection_reason="Only PDF files are accepted",
        )

    # Write to a temp file so PyMuPDF can open it
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        text = _extract_pdf_text(tmp_path, max_pages=3)
        if not text.strip():
            return DetectResponse(
                is_financial_report=False,
                rejection_reason="Could not extract text from PDF (scanned/image-only?)",
            )
        return _detect_metadata_from_text(text)
    finally:
        os.unlink(tmp_path)
        await file.seek(0)  # reset so the same file object can be read again if needed


@router.post("/upload", response_model=FilingOut, status_code=201)
async def upload_filing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    # company_id is now optional — if absent we auto-create from detected fields
    company_id: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    ticker: Optional[str] = Form(None),
    sector: Optional[str] = Form(None),
    fiscal_year: int = Form(...),
    currency: str = Form("INR"),
    unit_scale: str = Form("crores"),
    db: Session = Depends(get_db),
):
    # Resolve company
    if company_id:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
    else:
        if not company_name and not ticker:
            raise HTTPException(
                status_code=422,
                detail="Provide either company_id or at least company_name / ticker",
            )
        company = _get_or_create_company(company_name, ticker, sector, db)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    existing = db.query(Filing).filter(
        Filing.company_id == company.id,
        Filing.fiscal_year == fiscal_year,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A filing for {company.name} FY{fiscal_year} already exists",
        )

    dest_dir = Path(settings.upload_dir) / company.id / str(fiscal_year)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = dest_path.stat().st_size
    if file_size > settings.max_upload_size_mb * 1024 * 1024:
        dest_path.unlink()
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_size_mb} MB limit")

    filing = Filing(
        company_id=company.id,
        fiscal_year=fiscal_year,
        file_path=str(dest_path),
        file_name=file.filename,
        file_size_bytes=file_size,
        currency=currency,
        unit_scale=unit_scale,
        status=ProcessingStatus.PENDING,
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)

    prior = db.query(Filing).filter(
        Filing.company_id == company.id,
        Filing.fiscal_year == fiscal_year - 1,
        Filing.status == ProcessingStatus.COMPLETED,
    ).first()
    prior_id = prior.id if prior else None

    # Create Job record so frontend can poll live stage progress
    job = Job(filing_id=filing.id, stage="queued", progress_pct=0, status="queued")
    db.add(job)
    db.commit()

    background_tasks.add_task(_run_pipeline_bg, filing.id, prior_id)
    return filing


@router.get("/{filing_id}", response_model=FilingOut)
def get_filing(filing_id: str, db: Session = Depends(get_db)):
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    return filing


@router.delete("/{filing_id}", status_code=204)
def delete_filing(filing_id: str, db: Session = Depends(get_db)):
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    if filing.file_path and os.path.exists(filing.file_path):
        try:
            os.remove(filing.file_path)
        except OSError:
            pass
    try:
        from app.engines.embedding import delete_filing_chunks
        delete_filing_chunks(filing_id)
    except Exception:
        pass
    # Delete Job row first (FK constraint)
    db.query(Job).filter(Job.filing_id == filing_id).delete()
    db.delete(filing)
    db.commit()


@router.get("/{filing_id}/kpis", response_model=List[KPIOut])
def get_kpis(filing_id: str, verified_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(KPI).filter(KPI.filing_id == filing_id)
    if verified_only:
        q = q.filter(KPI.is_verified == True)  # noqa: E712
    return q.all()


@router.get("/{filing_id}/risks", response_model=List[RiskOut])
def get_risks(filing_id: str, db: Session = Depends(get_db)):
    return db.query(Risk).filter(Risk.filing_id == filing_id).all()


@router.get("/{filing_id}/flags", response_model=List[FootnoteFlagOut])
def get_flags(filing_id: str, db: Session = Depends(get_db)):
    return (
        db.query(FootnoteFlag)
        .filter(FootnoteFlag.filing_id == filing_id)
        .order_by(FootnoteFlag.ranking_score.desc())
        .all()
    )


@router.get("/{filing_id}/sections", response_model=List[SectionOut])
def get_sections(filing_id: str, db: Session = Depends(get_db)):
    return db.query(ReportSection).filter(ReportSection.filing_id == filing_id).all()


@router.get("/{filing_id}/promises", response_model=List[FootnoteFlagOut])
def get_promises(filing_id: str, db: Session = Depends(get_db)):
    """
    Returns prior-year promise tracking results for a filing.
    These are stored as FootnoteFlag rows with flag_type='prior_year_promise'.
    """
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    return (
        db.query(FootnoteFlag)
        .filter(
            FootnoteFlag.filing_id == filing_id,
            FootnoteFlag.flag_type == "prior_year_promise",
        )
        .order_by(FootnoteFlag.ranking_score.desc())
        .all()
    )


@router.get("/{filing_id}/dashboard", response_model=DashboardOut)
def get_dashboard(filing_id: str, db: Session = Depends(get_db)):
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    kpis     = db.query(KPI).filter(KPI.filing_id == filing_id).all()
    risks    = db.query(Risk).filter(Risk.filing_id == filing_id).all()
    flags    = (
        db.query(FootnoteFlag)
        .filter(FootnoteFlag.filing_id == filing_id)
        .order_by(FootnoteFlag.ranking_score.desc())
        .limit(10)
        .all()
    )
    sections = db.query(ReportSection).filter(ReportSection.filing_id == filing_id).all()

    from app.engines.peer_discovery import find_peers
    company = filing.company
    all_cos = [
        {"id": c.id, "name": c.name, "ticker": c.ticker,
         "sector": c.sector, "description": c.description}
        for c in db.query(Company).all()
    ]
    peers = find_peers(
        target_description=company.description or company.name,
        all_companies=all_cos,
        target_company_id=company.id,
        top_k=5,
    )

    return DashboardOut(
        filing=filing,
        company=company,
        kpis=kpis,
        risks=risks,
        top_flags=flags,
        sections=sections,
        peer_suggestions=[
            {"company_id": p.company_id, "name": p.company_name, "score": p.similarity_score}
            for p in peers
        ],
    )
