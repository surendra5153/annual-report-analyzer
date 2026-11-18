"""
Re-embed every processed filing into the current vector collection.

Needed once after changing the embedding model (MiniLM → bge-small), because
vectors from different models live in different spaces. Only parsing, chunking
and embedding run — KPIs, risks and summaries in the DB are left untouched.

Usage (from backend/):
    python -m scripts.reindex            # all filings
    python -m scripts.reindex <id> ...   # specific filings
"""
import os
import sys
import time

from loguru import logger

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Filing
from app.engines.chunking import chunk_document
from app.engines.embedding import delete_filing_chunks, embed_and_index_chunks
from app.engines.ingestion import ingest_pdf


def main(filing_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        q = db.query(Filing)
        if filing_ids:
            q = q.filter(Filing.id.in_(filing_ids))
        filings = q.all()
        logger.info(f"Re-indexing {len(filings)} filing(s) into '{settings.chroma_collection}'")

        for f in filings:
            if not os.path.exists(f.file_path):
                logger.warning(f"Skip {f.file_name}: PDF not found at {f.file_path}")
                continue
            t0 = time.time()
            doc = ingest_pdf(f.file_path)
            chunks = chunk_document(doc, f.id)
            delete_filing_chunks(f.id)
            embed_and_index_chunks(chunks["qa"] + chunks["extract"])
            logger.info(f"✓ {f.file_name} ({doc.page_count} pages) in {time.time() - t0:.1f}s")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
