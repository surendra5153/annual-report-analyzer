"""
ML status + metrics endpoints (consumed by the Model Lab page).
"""
import json
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter(prefix="/ml", tags=["ml"])

# ml/reports/metrics.json at the repo root, written by the training/eval scripts
_REPORTS_DIR = Path(__file__).resolve().parents[4] / "ml" / "reports"
_METRICS_PATH = _REPORTS_DIR / "metrics.json"


def _ollama_status() -> dict:
    base = (settings.openai_base_url or "").rstrip("/")
    if not base.endswith("/v1"):
        return {"provider": "remote", "base_url": base, "model": settings.openai_model}
    try:
        resp = httpx.get(base[: -len("/v1")] + "/api/tags", timeout=3)
        resp.raise_for_status()
        names = [m["name"] for m in resp.json().get("models", [])]
        model = settings.openai_model
        available = model in names or f"{model}:latest" in names
        return {"provider": "ollama", "up": True, "model": model, "model_available": available, "installed": names}
    except Exception as e:
        return {"provider": "ollama", "up": False, "model": settings.openai_model, "error": str(e)}


@router.get("/health")
def ml_health():
    from app.engines import embedding
    from app.ml import page_classifier, reranker

    return {
        "llm": _ollama_status(),
        "embedding": {"model": settings.embedding_model, "loaded": embedding._embedding_model is not None},
        "reranker": {
            "model": settings.reranker_model,
            "enabled": settings.enable_reranker,
            "loaded": reranker._reranker is not None,
        },
        "vector_collection": settings.chroma_collection,
        "page_classifier": {"trained_model": page_classifier.model_available()},
    }


def _report_json(path: Path, hint: str) -> dict:
    if not path.exists():
        return {"available": False, "message": hint}
    # NaN/Infinity (pandas missing values) are not valid JSON → null
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda _: None)}


@router.get("/metrics")
def ml_metrics():
    return _report_json(_METRICS_PATH, "Run the ml/ evaluation scripts to generate metrics.")


@router.get("/eda")
def ml_eda():
    return _report_json(_REPORTS_DIR / "eda.json", "Run ml/notebooks/02_eda to generate the EDA report.")


@router.get("/preprocessing")
def ml_preprocessing():
    return _report_json(_REPORTS_DIR / "preprocessing_summary.json",
                        "Run ml/notebooks/01_preprocessing to generate the summary.")


@router.get("/figures/{name}")
def ml_figure(name: str):
    path = (_REPORTS_DIR / "figures" / name).resolve()
    if path.parent != (_REPORTS_DIR / "figures").resolve() or path.suffix != ".png" or not path.exists():
        raise HTTPException(status_code=404, detail="Figure not found")
    return FileResponse(path, media_type="image/png")
