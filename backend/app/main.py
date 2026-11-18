"""
FastAPI application — local dev mode (SQLite + inline background tasks).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import os

from app.core.config import settings
from app.api.routes import companies, filings, qa, comparison, ml
from app.api.routes.jobs import router as jobs_router
from app.db.database import Base, engine, sync_added_columns

# Auto-create all tables (SQLite friendly)
Base.metadata.create_all(bind=engine)
sync_added_columns()

app = FastAPI(
    title="Annual Report Analysis System",
    description="AI-powered annual report analysis — NLP-07",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/api")
app.include_router(filings.router,   prefix="/api")
app.include_router(qa.router,        prefix="/api")
app.include_router(comparison.router, prefix="/api")
app.include_router(jobs_router,      prefix="/api")
app.include_router(ml.router,        prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0", "db": settings.database_url}


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting up — DB: {settings.database_url}")
    os.makedirs(settings.upload_dir, exist_ok=True)
    # Pre-warm the embedding model so the first upload doesn't pay the load cost
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _prewarm_embedding_model)


def _prewarm_embedding_model():
    try:
        from app.engines.embedding import get_embedding_model
        model = get_embedding_model()
        model.encode(["warmup"], show_progress_bar=False)
        from app.ml.reranker import get_reranker
        get_reranker()
        logger.info("Embedding model + reranker pre-warmed and ready")
        # Type every page of every processed report once, so the first numeric question is fast
        from app.db.database import SessionLocal
        from app.db.models import Filing, ProcessingStatus
        from app.ml.statement_index import statement_index
        db = SessionLocal()
        try:
            for f in db.query(Filing).filter(Filing.status == ProcessingStatus.COMPLETED).all():
                statement_index(f.id)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Embedding model pre-warm failed (non-fatal): {e}")
