"""
Filing Watch Agent
Periodically polls BSE/NSE for new annual reports for tracked companies.
Rate-limited and respectful of public sources.
"""
import os
import time
import hashlib
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Company, Filing, ProcessingStatus
from app.workers.tasks import process_filing_task


BSE_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
HEADERS = {
    "User-Agent": "AnnualReportAnalyzer/1.0 (research project; contact@example.com)",
    "Accept": "application/json",
}
RATE_LIMIT_SECONDS = 5   # wait between requests


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def _already_downloaded(company_id: str, fiscal_year: int, db: Session) -> bool:
    return db.query(Filing).filter(
        Filing.company_id == company_id,
        Filing.fiscal_year == fiscal_year,
    ).first() is not None


def check_new_filings(company: Company, db: Session) -> None:
    """
    Check BSE for new annual reports for a given company.
    If a new filing is found, download it and queue it for processing.
    This is a best-effort, rate-limited scrape — not a guaranteed real-time feed.
    """
    if not company.ticker:
        logger.debug(f"Skipping {company.name}: no ticker configured")
        return

    logger.info(f"Checking filings for {company.name} ({company.ticker})")
    time.sleep(RATE_LIMIT_SECONDS)

    try:
        # BSE announcements endpoint (annual reports category = 30)
        params = {
            "scrip_cd": company.ticker,
            "ann_type": "30",    # Annual Report category
            "page_no": "1",
        }
        with httpx.Client(timeout=30, headers=HEADERS) as client:
            response = client.get(BSE_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

        announcements = data.get("Table", [])
        for ann in announcements[:3]:   # check latest 3 announcements
            pdf_url = ann.get("ATTACHMENTNAME", "")
            fiscal_year = _extract_fiscal_year(ann.get("ANNOUNCEMENT_DATE", ""))
            if not pdf_url or not fiscal_year:
                continue
            if _already_downloaded(company.id, fiscal_year, db):
                continue

            # Download the PDF
            pdf_path = _download_pdf(pdf_url, company, fiscal_year)
            if not pdf_path:
                continue

            # Create a Filing record
            filing = Filing(
                company_id=company.id,
                fiscal_year=fiscal_year,
                file_path=str(pdf_path),
                file_name=pdf_path.name,
                file_size_bytes=pdf_path.stat().st_size,
                status=ProcessingStatus.PENDING,
            )
            db.add(filing)
            db.commit()
            db.refresh(filing)

            logger.info(f"New filing queued: {company.name} FY{fiscal_year}")
            process_filing_task.delay(filing.id)

    except httpx.HTTPError as e:
        logger.warning(f"HTTP error checking filings for {company.name}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in filing watch for {company.name}: {e}")


def _extract_fiscal_year(date_str: str) -> Optional[int]:
    """Extract fiscal year from an announcement date string."""
    import re
    match = re.search(r"20(\d{2})", date_str)
    if match:
        return 2000 + int(match.group(1))
    return None


def _download_pdf(url: str, company: Company, fiscal_year: int) -> Optional[Path]:
    """Download a PDF to the upload directory. Returns local path or None on failure."""
    dest_dir = Path(settings.upload_dir) / company.ticker / str(fiscal_year)
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.Client(timeout=120, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()

        filename = f"{company.ticker}_{fiscal_year}_{_file_hash(resp.content)}.pdf"
        dest = dest_dir / filename
        dest.write_bytes(resp.content)
        logger.info(f"Downloaded: {dest}")
        return dest
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return None
