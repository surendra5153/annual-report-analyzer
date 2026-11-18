"""
Cross-encoder reranker (pre-trained ms-marco MiniLM, runs on CPU).

A bi-encoder embeds query and passage separately; a cross-encoder reads them
together and scores relevance directly — slower, so it is applied only to the
~30 fused candidates, but much more precise.
"""
import math
from typing import List, Optional

from loguru import logger

from app.core.config import settings

_reranker = None
_load_failed = False


def get_reranker():
    global _reranker, _load_failed
    if _reranker is None and not _load_failed and settings.enable_reranker:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker: {settings.reranker_model}")
            _reranker = CrossEncoder(settings.reranker_model, max_length=512, device="cpu")
        except Exception as e:  # missing weights offline, etc. — retrieval still works without it
            logger.warning(f"Reranker unavailable, falling back to RRF order: {e}")
            _load_failed = True
    return _reranker


def rerank_scores(query: str, passages: List[str]) -> Optional[List[float]]:
    """Relevance probabilities in [0, 1] (sigmoid of logits), or None if no reranker."""
    model = get_reranker()
    if model is None or not passages:
        return None
    logits = model.predict([(query, p) for p in passages], show_progress_bar=False)
    return [1.0 / (1.0 + math.exp(-float(x))) for x in logits]
