"""
Celery tasks for async processing and scheduled filing watch.
"""
from celery import shared_task
from loguru import logger

from app.workers.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Company, Filing, ProcessingStatus
from app.services.pipeline import run_full_pipeline


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_filing_task(self, filing_id: str, prior_filing_id: str = None):
    """
    Async task: run the full processing pipeline for a filing.
    """
    logger.info(f"Task started: process_filing {filing_id}")
    db = SessionLocal()
    try:
        run_full_pipeline(filing_id, db, prior_filing_id)
    except Exception as exc:
        logger.error(f"Task failed for {filing_id}: {exc}")
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for filing {filing_id}")
    finally:
        db.close()


@celery_app.task
def filing_watch_task():
    """
    Scheduled task: check for new filings for tracked companies.
    Polls BSE/NSE for companies marked as is_tracked=True.
    """
    from app.workers.filing_watcher import check_new_filings
    logger.info("Filing watch task started")
    db = SessionLocal()
    try:
        tracked = db.query(Company).filter(Company.is_tracked == True).all()  # noqa: E712
        logger.info(f"Watching {len(tracked)} tracked companies")
        for company in tracked:
            try:
                check_new_filings(company, db)
            except Exception as e:
                logger.warning(f"Filing watch failed for {company.name}: {e}")
    finally:
        db.close()
