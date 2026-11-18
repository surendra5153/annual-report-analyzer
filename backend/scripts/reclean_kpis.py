"""
Apply KPI cleansing to filings processed before it existed (or re-apply after
changing the rules). Idempotent: works from KPI.raw_value.

Processes each company's filings oldest-first, so the stale-copy rule can
compare against the already-cleaned prior year.

Usage (from backend/):  python -m scripts.reclean_kpis [filing_id ...]
"""
import os
import sys

import fitz
from loguru import logger

from app.db.database import SessionLocal
from app.db.models import Filing, ProcessingStatus
from app.services.kpi_cleaning import clean_filing_kpis


def main(ids: list[str]) -> None:
    db = SessionLocal()
    try:
        q = db.query(Filing).filter(Filing.status == ProcessingStatus.COMPLETED)
        if ids:
            q = q.filter(Filing.id.in_(ids))
        for f in q.order_by(Filing.company_id, Filing.fiscal_year).all():
            if not os.path.exists(f.file_path):
                logger.warning(f"skip {f.file_name}: PDF missing")
                continue
            with fitz.open(f.file_path) as doc:
                pages = [p.get_text() for p in doc]
            print(f.file_name, clean_filing_kpis(f, pages, db))
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
