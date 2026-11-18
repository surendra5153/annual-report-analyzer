from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # LLM — defaults point at a LOCAL Ollama server (OpenAI-compatible API).
    # Runtime makes zero cloud calls. Swap openai_model to "finsumm" once the
    # fine-tuned model is created in Ollama (see ml/export/Modelfile).
    openai_api_key: str = "ollama"          # Ollama ignores the key, client requires one
    openai_base_url: str = "http://localhost:11434/v1"
    openai_model: str = "qwen2.5:3b"
    openai_vision_model: str = ""           # vision disabled for local runtime
    llm_timeout_seconds: float = 300.0      # local generation on a 4 GB GPU can be slow

    # Database — defaults to SQLite for local dev
    database_url: str = "sqlite:///./annual_reports.db"

    # Vector store — local persistent path (no server needed)
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_local_path: str = "./chroma_db"

    # Redis (only needed if running Celery)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 100

    # Filing watch
    filing_watch_interval_hours: int = 24

    # App
    secret_key: str = "change-me-in-production"
    debug: bool = True
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ]

    # Chunking — QA chunks kept short so encode() is fast; extraction chunks larger
    qa_chunk_size: int = 400
    qa_chunk_overlap: int = 80
    extraction_chunk_size: int = 1000
    extraction_chunk_overlap: int = 100

    # Embedding / retrieval (pre-trained, run locally on CPU)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    chroma_collection: str = "annual_reports_v2"   # v2 = bge vector space (re-index old filings)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_reranker: bool = True
    retrieval_candidates: int = 30          # per retriever, before RRF + rerank
    qa_use_kpi_facts: bool = True           # give Q&A the extracted KPI table as a source (notebook 05)
    # Q&A configuration selected on the dev set (notebook 06, config H)
    qa_model: str = "finsight-qwen"         # qwen2.5:3b with an 8k context (ml/export/Modelfile.finsight-qwen)
    qa_statement_pages: bool = True         # add whole financial-statement pages for numeric questions
    qa_facts_with_statements: bool = False  # drop the KPI table when statement pages were found
    qa_table_reader: bool = True            # answer confident statement-cell lookups deterministically (no LLM)

    # Vision extraction — per-page chart descriptions (slow, uses LLM tokens)
    enable_vision_extraction: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.chroma_local_path, exist_ok=True)
