from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # LLM — defaults point at Gemini's OpenAI-compatible endpoint.
    # To switch to OpenAI: set openai_base_url="" and use an sk-... key.
    openai_api_key: str = ""
    openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    openai_model: str = "gemini-3.5-flash-lite"
    openai_vision_model: str = "gemini-3.5-flash-lite"  # same model handles vision

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

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Vision extraction — per-page chart descriptions (slow, uses LLM tokens)
    enable_vision_extraction: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.chroma_local_path, exist_ok=True)
