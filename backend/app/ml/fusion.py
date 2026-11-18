"""
Reciprocal Rank Fusion (Cormack et al., 2009).

    RRF(d) = Σ_{r ∈ rankings} 1 / (k + rank_r(d))

Rank-based, so it needs no score calibration between BM25 (unbounded) and
cosine similarity (−1..1). k = 60 is the value from the original paper.
"""
from typing import Dict, Hashable, List, Sequence


def reciprocal_rank_fusion(rankings: Sequence[Sequence[Hashable]], k: int = 60) -> List[Hashable]:
    scores: Dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)
