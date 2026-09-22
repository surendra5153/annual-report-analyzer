"""
Auto Peer Discovery Engine
Suggests comparable companies by embedding similarity over business descriptions.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer
from loguru import logger
import numpy as np

from app.core.config import settings

_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


@dataclass
class PeerSuggestion:
    company_id: str
    company_name: str
    ticker: str
    sector: str
    similarity_score: float
    reason: str


def find_peers(
    target_description: str,
    all_companies: List[Dict],
    target_company_id: str,
    top_k: int = 5,
) -> List[PeerSuggestion]:
    """
    Find the top-k most similar companies to a target company
    based on cosine similarity of their business description embeddings.

    Args:
        target_description: business description of the company to match
        all_companies: list of dicts with keys: id, name, ticker, sector, description
        target_company_id: exclude the target itself from results
        top_k: number of suggestions to return

    Returns:
        List of PeerSuggestion sorted by similarity (descending)
    """
    if not all_companies or not target_description.strip():
        return []

    model = _get_model()

    # Filter candidates (same sector preferred, but search all)
    candidates = [c for c in all_companies if c.get("id") != target_company_id]
    if not candidates:
        return []

    candidate_descriptions = [c.get("description", "") or c.get("name", "") for c in candidates]
    all_texts = [target_description] + candidate_descriptions

    embeddings = model.encode(all_texts, show_progress_bar=False, normalize_embeddings=True)
    target_emb = embeddings[0]
    candidate_embs = embeddings[1:]

    # Cosine similarity (embeddings are L2-normalized so dot product = cosine)
    scores = (candidate_embs @ target_emb).tolist()

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

    suggestions = []
    for idx, score in indexed:
        c = candidates[idx]
        suggestions.append(PeerSuggestion(
            company_id=c.get("id", ""),
            company_name=c.get("name", ""),
            ticker=c.get("ticker", ""),
            sector=c.get("sector", ""),
            similarity_score=round(float(score), 4),
            reason=f"Business description similarity: {score:.1%}",
        ))

    logger.info(f"Found {len(suggestions)} peer suggestions for company {target_company_id}")
    return suggestions
