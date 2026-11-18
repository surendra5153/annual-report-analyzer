"""
Page-type classification for annual-report pages.

Uses the PageClassifier we train in ml/notebooks/03_model_selection
(models/page_classifier/model.joblib) when it is present, and falls back to
the rule-based heading labeller otherwise, so the pipeline always works.
"""
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.ml.label_pages import label_document
from app.ml.text_clean import clean_document, normalize_unicode

MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "page_classifier" / "model.joblib"
# Fine-grained rule labels and the PageClassifier's coarse taxonomy (statement / notes / …)
STATEMENT_TYPES = {"statement", "balance_sheet", "profit_loss", "cash_flow", "equity_changes", "notes"}

_model = None
_load_failed = False


def _load():
    global _model, _load_failed
    if _model is None and not _load_failed:
        if not MODEL_PATH.exists():
            _load_failed = True
            return None
        try:
            import joblib
            _model = joblib.load(MODEL_PATH)
            logger.info(f"Loaded PageClassifier from {MODEL_PATH}")
        except Exception as e:  # incompatible sklearn version etc.
            logger.warning(f"PageClassifier unavailable, using heading rules: {e}")
            _load_failed = True
    return _model


def model_available() -> bool:
    return _load() is not None


def classify_pages(page_texts: List[str]) -> List[str]:
    """Return one page-type label per page of a single report."""
    model = _load()
    if model is None:
        return [label for label, _ in label_document([normalize_unicode(t) for t in page_texts])]

    import pandas as pd
    from app.ml.text_clean import page_features

    cleaned = clean_document(page_texts).pages
    n = len(page_texts)
    rows = []
    for i, (raw, text) in enumerate(zip(page_texts, cleaned)):
        rows.append({
            "clean_text": text,
            "head_text": normalize_unicode(raw)[:400].lower(),  # same as notebook 01
            **page_features(text),
            "rel_position": round((i + 1) / max(n, 1), 4),
        })
    frame = pd.DataFrame(rows)
    return list(model.predict(frame))


def statement_pages(page_texts: List[str], labels: Optional[List[str]] = None) -> List[int]:
    """Indices of financial-statement / notes pages."""
    labels = labels or classify_pages(page_texts)
    return [i for i, l in enumerate(labels) if l in STATEMENT_TYPES]
