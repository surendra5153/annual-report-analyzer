import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
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

def _sample_pdf_pages(path: str, head: int = 5, spread: int = 20) -> tuple[list[str], int]:
    """Return (page_texts, page_count) for the first *head* pages plus *spread*
    pages evenly spaced across the document.

    Exchange filings often open with a cover letter and an AGM notice, so the
    report itself (and its statements) can start dozens of pages in.
    """
    try:
        import pymupdf
        doc = pymupdf.open(path)
        n = len(doc)
        idx = set(range(min(n, head)))
        if n > head and spread:
            step = max(1, (n - head) // spread)
            idx.update(range(head, n, step))
        pages = [doc[i].get_text("text") for i in sorted(idx)]
        doc.close()
        return pages, n
    except Exception:
        return [], 0


# Distinct signals that a document is an annual report / financial filing.
_APOS = "['’�]?"
_FINANCIAL_SIGNALS = {
    "annual_report":  rf"annual report|form 10-k|form 20-f",
    "balance_sheet":  rf"balance sheet|statement of financial position",
    "profit_loss":    rf"statement of profit and loss|profit and loss|income statement",
    "cash_flow":      rf"cash flow",
    "auditor":        rf"independent auditor|auditor{_APOS}s{_APOS} report",
    "notes":          rf"notes to (?:the )?(?:standalone |consolidated )?financial statements",
    "board_report":   rf"board{_APOS}s report|directors{_APOS} report|board of directors",
    "mdna":           rf"management discussion",
    "governance":     rf"corporate governance",
    "cin":            rf"\bcin\b",
    "period":         rf"financial year|fiscal year|\bfy\s?\d{{2}}",
    "inr_units":      rf"₹|\bcrores?\b|\blakhs?\b",
}
_STRONG_EVIDENCE = 4   # distinct signals needed to accept regardless of the LLM


def _financial_evidence(pages: list[str], page_count: int) -> tuple[set[str], list[int]]:
    """Return (distinct signals found, per-page signal counts)."""
    import re
    found: set[str] = set()
    per_page = []
    for text in pages:
        low = text.lower()
        hits = {k for k, pat in _FINANCIAL_SIGNALS.items() if re.search(pat, low)}
        found |= hits
        per_page.append(len(hits))
    if page_count >= 40:
        found.add("long_document")
    return found, per_page


_REPORT_SUBJECT = re.compile(
    r"annual\s+report|integrated\s+(?:annual\s+)?report|form\s+10-?k|form\s+20-?f"
    r"|business\s+responsibility.{0,40}report|financial\s+statements|regulation\s*34\b",
    re.IGNORECASE,
)
_SUBJECT_LINE = re.compile(r"^\s*sub(?:ject)?\s*[:\-.]\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _first_page(pages: list[str]) -> str:
    """First of the opening pages with real text — image-only covers fall through."""
    for text in pages[:3]:
        if len(text.strip()) >= 80:
            return text
    return pages[0] if pages else ""


def _subject_from_first_page(text: str) -> tuple[Optional[str], bool]:
    """(subject, says_annual_report) from a cover letter's 'Sub:' line or the cover title.

    BSE/NSE filings open with a letter to the exchange whose subject names the
    document ("Sub: Annual Report for FY 2024-25"); standalone reports open with
    a title page. Either way page 1 says what the document is.
    """
    lines = [" ".join(l.split()) for l in text.splitlines() if l.strip()]
    m = _SUBJECT_LINE.search(text)
    if m:
        # Subjects often wrap onto a second line
        i = next((k for k, l in enumerate(lines) if l.lower().startswith("sub")), 0)
        subject = " ".join([m.group(1).strip()] + lines[i + 1:i + 2])[:160]
        return subject, bool(_REPORT_SUBJECT.search(subject))
    title = " ".join(lines[:8])
    hit = _REPORT_SUBJECT.search(title)
    if hit:
        return hit.group(0), True
    return None, False


def _classify_first_page(text: str) -> tuple[Optional[str], Optional[bool]]:
    """Ask the LLM about page 1 only. Returns (subject, is_annual_report); None if the call fails."""
    from app.core.llm_client import chat_complete_json
    try:
        data = chat_complete_json(
            messages=[
                {"role": "system", "content": (
                    "This is the FIRST PAGE of an uploaded PDF. State its subject in a few words "
                    "and whether the document is a company's annual report / annual financial "
                    "filing (annual report, integrated report, 10-K, 20-F). A cover letter to a "
                    "stock exchange whose subject is the annual report counts as yes.\n"
                    "Schema: {subject: str, is_annual_report: bool}"
                )},
                {"role": "user", "content": text.strip()[:1500]},
            ],
            max_tokens=60,
        )
        verdict = data.get("is_annual_report")
        return data.get("subject"), (bool(verdict) if verdict is not None else None)
    except Exception:
        return None, None


def _page1_verdict(pages: list[str]) -> tuple[Optional[str], Optional[bool]]:
    """Decide the document type from the first page: regex first, LLM only if undecided."""
    first = _first_page(pages)
    subject, says_report = _subject_from_first_page(first)
    if says_report:
        return subject, True
    llm_subject, verdict = _classify_first_page(first)
    return llm_subject or subject, verdict


def _confidence(page1_yes: bool, strong: bool) -> str:
    if page1_yes and strong:
        return "high"
    return "medium" if page1_yes or strong else "low"


def _llm_excerpt(pages: list[str], per_page: list[int], limit: int = 3000) -> str:
    """Cover page plus the pages densest in financial signals, capped at *limit* chars."""
    if not pages:
        return ""
    picks = [0] + sorted(range(1, len(pages)), key=lambda i: -per_page[i])[:2]
    share = limit // len(picks)
    return "\n---\n".join(pages[i].strip()[:share] for i in picks)


def _year_from_filename(filename: str) -> Optional[int]:
    """'Reliance FY26.pdf' → 2026, 'AR 2024-25.pdf' → 2025, 'HAL FY2025.pdf' → 2025."""
    import re
    m = re.search(r"(20\d{2})\s*[-_–]\s*(\d{2})(?!\d)", filename)
    if m:
        return 2000 + int(m.group(2))
    m = re.search(r"FY\s*[-_]?\s*(?:20)?(\d{2})(?!\d)", filename, re.IGNORECASE)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"(?<!\d)(20\d{2})(?!\d)", filename)
    return int(m.group(1)) if m else None


_COMPANY_LINE = re.compile(r"\s*[A-Z][A-Za-z&.,'\- ]{2,60}\b(?:Limited|Ltd\.?)\s*")
_NOT_ISSUER = re.compile(r"stock exchange|\bbse\b|\bnse\b|depository|registrar|share transfer", re.IGNORECASE)


def _company_from_pages(pages: list[str]) -> Optional[str]:
    """The issuer's name: page 1's letterhead / cover if it has one, else the most
    frequent short '… Limited' line (usually the running page header).

    Conglomerate reports repeat subsidiaries' names in headers more often than
    the parent's, so the first page is trusted first.
    """
    from collections import Counter
    head = [l for l in _first_page(pages).splitlines() if l.strip()][:15]
    for line in head:
        if _COMPANY_LINE.fullmatch(line) and not _NOT_ISSUER.search(line):
            return " ".join(line.split())
    names = Counter(
        " ".join(line.split())
        for text in pages for line in text.splitlines()
        if _COMPANY_LINE.fullmatch(line) and not _NOT_ISSUER.search(line)
    )
    return names.most_common(1)[0][0] if names else None


def _detect_metadata_from_text(pages: list[str], page_count: int, filename: str = "") -> DetectResponse:
    """Validate the PDF (page 1 decides) and extract filing metadata (patterns + LLM)."""
    from app.core.llm_client import chat_complete_json

    signals, per_page = _financial_evidence(pages, page_count)
    strong = len(signals) >= _STRONG_EVIDENCE

    # Quick reject non-financial docs
    if not signals - {"long_document"}:
        return DetectResponse(
            is_financial_report=False,
            rejection_reason="Document does not appear to be a financial report",
            confidence="medium",
        )

    # The document type is decided from page 1 alone. Strong structural evidence
    # elsewhere still overrides a "no" (a 3B model is easily fooled by AGM notices);
    # if the LLM call fails we accept on the keyword evidence, at low confidence.
    subject, page1 = _page1_verdict(pages)
    is_financial = bool(page1) or strong or page1 is None
    if not is_financial:
        return DetectResponse(
            is_financial_report=False,
            rejection_reason=(f"Page 1 looks like: '{subject}', not an annual report" if subject
                              else "Document does not appear to be a financial report"),
            confidence="medium",
        )
    confidence = _confidence(bool(page1), strong)

    text = "\n".join(pages[:3])

    # Try pattern-based extraction first (instant)
    patterns = {
        "fiscal_year": re.compile(r'\b(?:FY|fiscal year|financial year|for the year ended|year ending)\s*[:\-]?\s*(?:20)?(\d{2})(?:\s*[-/]\s*(?:20)?(\d{2}))?', re.IGNORECASE),
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
        quick_data["unit_scale"] = unit_match.group(1).lower().rstrip('s') + 's'   # match the UI's options

    system_prompt = (
        "Extract metadata from annual report PDF text. Return JSON only.\n\n"
        "Schema: {company_name: str|null, ticker: str|null, fiscal_year: int|null, "
        "currency: str|null, unit_scale: str|null, report_type: str|null}\n\n"
        "Rules:\n"
        "- fiscal_year = year period ENDS (FY 2023-24 → 2024)\n"
        "- unit_scale: crores|lakhs|millions|billions|units\n"
        "- currency: INR, USD, EUR, etc."
    )

    if fy := _year_from_filename(filename):
        quick_data.setdefault("fiscal_year", fy)
    if name := _company_from_pages(pages):
        quick_data["company_name"] = name

    try:
        data = chat_complete_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _llm_excerpt(pages, per_page)},
            ],
            max_tokens=250,
        )

        # Merge pattern-based results with LLM results. The LLM takes precedence,
        # except for company and year: the running page header and "FY 2024-25"
        # parse deterministically, while the 3B model says "Your Company" or
        # takes the start year.
        result = {**quick_data, **{k: v for k, v in data.items() if v is not None}}
        for key in ("company_name", "fiscal_year"):
            if quick_data.get(key):
                result[key] = quick_data[key]
    except Exception:
        # Fallback to pattern-based if LLM fails
        result = quick_data

    return DetectResponse(
        is_financial_report=True,
        rejection_reason=None,
        company_name=result.get("company_name"),
        ticker=result.get("ticker"),
        fiscal_year=result.get("fiscal_year"),
        currency=result.get("currency", "INR"),
        unit_scale=result.get("unit_scale", "crores"),
        report_type=result.get("report_type") or "Annual Report",
        confidence=confidence,
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
        pages, page_count = _sample_pdf_pages(tmp_path)
        if not "".join(pages).strip():
            return DetectResponse(
                is_financial_report=False,
                rejection_reason="Could not extract text from PDF (scanned/image-only?)",
            )
        return _detect_metadata_from_text(pages, page_count, file.filename)
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


@router.get("/{filing_id}/pdf")
def get_filing_pdf(filing_id: str, db: Session = Depends(get_db)):
    """Stream the original PDF (used by the in-app viewer for citation highlights)."""
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    if not filing.file_path or not os.path.exists(filing.file_path):
        raise HTTPException(status_code=404, detail="PDF file is no longer on disk")
    return FileResponse(
        filing.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filing.file_name}"'},
    )


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
