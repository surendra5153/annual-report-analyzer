"""
Full processing pipeline service.
Orchestrates: ingest → chunk → embed → summarize → KPI extract → risks → footnotes → anomalies

Emits live stage/progress via the jobs table so the frontend can show a
granular progress indicator. Per-stage wall-clock timing is logged so
bottlenecks are always visible in the server log.
"""
import time
from typing import Optional, List
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import Filing, Job, KPI, Risk, FootnoteFlag, ReportSection, ProcessingStatus
from app.engines.ingestion import ingest_pdf, PageContent
from app.engines.chunking import chunk_document
from app.engines.embedding import embed_and_index_chunks
from app.engines.summarizer import summarize_document
from app.engines.kpi_extractor import extract_kpis
from app.engines.risk_classifier import classify_risks
from app.engines.footnote_engine import run_footnote_engine
from app.engines.anomaly_detector import detect_anomalies
from app.services.kpi_cleaning import clean_filing_kpis

STAGES = [
    ("parsing",        "Parsing PDF",              10),
    ("chunking",       "Chunking document",        20),
    ("embedding",      "Building search index",    35),
    ("summarizing",    "Summarizing sections",     50),
    ("kpi_extraction", "Extracting KPIs",          65),
    ("risk_analysis",  "Classifying risks",        78),
    ("footnote_check", "Cross-checking footnotes", 90),
    ("anomaly_detect", "Detecting anomalies",      97),
    ("done",           "Done",                    100),
]


def _set_stage(job: Job, stage: str, db: Session) -> None:
    pct = next((p for s, _, p in STAGES if s == stage), job.progress_pct)
    job.stage = stage
    job.progress_pct = pct
    job.status = "running" if stage != "done" else "done"
    db.commit()


def _text_to_pages(full_text: str) -> List[PageContent]:
    """
    Reconstruct lightweight PageContent objects from stored full_text.
    The footnote engine only reads page.text — no tables or images needed.
    Splits the text into ~500-char blocks, each treated as one page.
    Zero PDF I/O — reads straight from the DB column.
    """
    block_size = 500
    return [
        PageContent(page_number=i + 1, text=full_text[i:i + block_size])
        for i in range(0, len(full_text), block_size)
    ]


def run_full_pipeline(filing_id: str, db: Session, prior_filing_id: Optional[str] = None) -> None:
    filing: Filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise ValueError(f"Filing {filing_id} not found")

    job = db.query(Job).filter(Job.filing_id == filing_id).first()
    if not job:
        job = Job(filing_id=filing_id, stage="queued", progress_pct=0, status="queued")
        db.add(job)
        db.commit()
        db.refresh(job)

    filing.status = ProcessingStatus.PROCESSING
    db.commit()

    try:
        logger.info(f"=== Pipeline start: {filing.file_name} ===")
        pipeline_start = time.time()

        # ── Stage 1: Ingest ────────────────────────────────────────────────
        _set_stage(job, "parsing", db)
        t0 = time.time()
        doc = ingest_pdf(filing.file_path)
        filing.page_count = doc.page_count
        # Store full text — eliminates re-parsing PDF for prior-year footnote checks
        filing.full_text = doc.full_text[:500000]
        db.commit()
        logger.info(f"[timing] parsing: {time.time()-t0:.1f}s  ({doc.page_count} pages, {len(doc.all_tables)} tables)")

        # ── Stage 2: Chunk ─────────────────────────────────────────────────
        _set_stage(job, "chunking", db)
        t0 = time.time()
        chunks = chunk_document(doc, filing_id)
        logger.info(f"[timing] chunking: {time.time()-t0:.1f}s  (qa={len(chunks['qa'])}, extract={len(chunks['extract'])})")

        # ── Stage 3: Embed & index ─────────────────────────────────────────
        _set_stage(job, "embedding", db)
        t0 = time.time()
        embed_and_index_chunks(chunks["qa"] + chunks["extract"])
        logger.info(f"[timing] embedding: {time.time()-t0:.1f}s")

        # ── Stage 4: Summarize sections ────────────────────────────────────
        _set_stage(job, "summarizing", db)
        t0 = time.time()
        section_results = summarize_document(doc.pages)
        risk_section_text = ""
        for sr in section_results:
            db.add(ReportSection(
                filing_id=filing_id,
                section_name=sr.section_name,
                summary=sr.summary,
                raw_text=sr.raw_text[:50000],
                start_page=sr.start_page,
                end_page=sr.end_page,
            ))
            if sr.section_name == "risk_factors":
                risk_section_text = sr.raw_text
        db.commit()
        logger.info(f"[timing] summarizing: {time.time()-t0:.1f}s  ({len(section_results)} sections)")

        # ── Stage 5: KPI extraction ────────────────────────────────────────
        _set_stage(job, "kpi_extraction", db)
        t0 = time.time()
        text_chunks = [c.text for c in chunks["extract"]]
        kpi_results = extract_kpis(
            tables=doc.all_tables,
            text_chunks=text_chunks,
            currency=filing.currency,
            unit_scale=filing.unit_scale,
            pages=doc.pages,
        )
        for kpi in kpi_results:
            db.add(KPI(
                filing_id=filing_id,
                name=kpi.name,
                value=kpi.value,
                unit=kpi.unit,
                currency=kpi.currency,
                page_number=kpi.page_number,
                source_text=kpi.source_text[:500] if kpi.source_text else None,
                is_verified=kpi.is_verified,
                verification_note=kpi.verification_note,
                category=kpi.category,
            ))
        db.commit()
        # Unit normalisation + accounting-consistency rules (same as notebook 01)
        try:
            clean_filing_kpis(filing, [p.text for p in doc.pages], db)
        except Exception as e:  # never fail the whole pipeline on cleaning
            logger.warning(f"KPI cleaning skipped: {e}")
            db.rollback()
        logger.info(f"[timing] kpi_extraction: {time.time()-t0:.1f}s  ({len(kpi_results)} KPIs)")

        # ── Stage 6: Risk classification ───────────────────────────────────
        _set_stage(job, "risk_analysis", db)
        t0 = time.time()
        risk_results = classify_risks(doc.pages, risk_section_text)
        for risk in risk_results:
            db.add(Risk(
                filing_id=filing_id,
                category=risk.category,
                title=risk.title,
                description=risk.description,
                severity=risk.severity,
                page_number=risk.page_number,
                source_text=risk.source_text[:500] if risk.source_text else None,
            ))
        db.commit()
        logger.info(f"[timing] risk_analysis: {time.time()-t0:.1f}s  ({len(risk_results)} risks)")

        # ── Stage 7: Footnote & Consistency Engine ─────────────────────────
        _set_stage(job, "footnote_check", db)
        t0 = time.time()
        prior_pages = None
        if prior_filing_id:
            prior_filing = db.query(Filing).filter(Filing.id == prior_filing_id).first()
            if prior_filing:
                if prior_filing.full_text:
                    # Fast path: read stored text — no PDF I/O (~0s vs ~55s)
                    prior_pages = _text_to_pages(prior_filing.full_text)
                    logger.info(f"Prior year text loaded from DB ({len(prior_pages)} virtual pages)")
                else:
                    # Fallback for filings processed before this change
                    try:
                        prior_doc = ingest_pdf(prior_filing.file_path)
                        prior_pages = prior_doc.pages
                        logger.info("Prior year loaded via ingest_pdf (full_text not stored)")
                    except Exception as e:
                        logger.warning(f"Could not load prior filing: {e}")

        footnote_flags = run_footnote_engine(doc.pages, prior_pages)
        for flag in footnote_flags:
            db.add(FootnoteFlag(
                filing_id=filing_id,
                flag_type=flag.flag_type,
                title=flag.title,
                description=flag.description,
                severity=flag.severity,
                footnote_text=flag.footnote_text[:1000] if flag.footnote_text else None,
                narrative_text=flag.narrative_text[:1000] if flag.narrative_text else None,
                prior_year_text=flag.prior_year_text[:500] if flag.prior_year_text else None,
                page_number=flag.page_number,
                ranking_score=flag.ranking_score,
            ))
        db.commit()
        logger.info(f"[timing] footnote_check: {time.time()-t0:.1f}s  ({len(footnote_flags)} flags)")

        # ── Stage 8: Anomaly detection ─────────────────────────────────────
        _set_stage(job, "anomaly_detect", db)
        t0 = time.time()
        if prior_filing_id:
            prior_kpis = db.query(KPI).filter(KPI.filing_id == prior_filing_id).all()
            prior_lookup = {k.name: k.value for k in prior_kpis if k.value is not None}
            current_lookup = {k.name: k.value for k in
                              db.query(KPI).filter(KPI.filing_id == filing_id).all()
                              if k.value is not None}
            anomalies = detect_anomalies(current_lookup, prior_lookup)
            for a in anomalies:
                if a.severity in ("high", "critical"):
                    db.add(FootnoteFlag(
                        filing_id=filing_id,
                        flag_type="anomaly",
                        title=f"KPI anomaly: {a.kpi_name}",
                        description=a.description,
                        severity=a.severity,
                        ranking_score=1.0 if a.severity == "critical" else 0.7,
                    ))
            db.commit()
            logger.info(f"[timing] anomaly_detect: {time.time()-t0:.1f}s")

        # ── Done ───────────────────────────────────────────────────────────
        _set_stage(job, "done", db)
        filing.status = ProcessingStatus.COMPLETED
        db.commit()
        total = time.time() - pipeline_start
        logger.info(f"=== Pipeline complete: {filing.file_name}  total={total:.1f}s ===")

    except Exception as e:
        logger.exception(f"Pipeline failed for {filing_id}: {e}")
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        filing.status = ProcessingStatus.FAILED
        filing.error_message = str(e)
        db.commit()
        raise
