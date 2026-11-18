"""
Okapi BM25 sparse retrieval, implemented from scratch.

    score(D, Q) = Σ_{t ∈ Q} IDF(t) · f(t, D) · (k1 + 1)
                              ───────────────────────────────────
                              f(t, D) + k1 · (1 − b + b · |D| / avgdl)

    IDF(t) = ln( (N − n(t) + 0.5) / (n(t) + 0.5) + 1 )

Dense embeddings miss exact financial terms ("EBITDA", "Ind AS 116",
note numbers); BM25 catches them. The two are combined with Reciprocal
Rank Fusion (see fusion.py).
"""
import math
import re
from collections import Counter
from typing import List, Sequence, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")

# Small stop-word list: function words only, so financial terms survive
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the "
    "this to was were what which with how did does do during year".split()
)


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class BM25:
    def __init__(self, corpus: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs: List[Counter] = []
        self.doc_lens: List[int] = []
        df: Counter = Counter()

        for doc in corpus:
            tokens = tokenize(doc)
            freqs = Counter(tokens)
            self.doc_freqs.append(freqs)
            self.doc_lens.append(len(tokens))
            df.update(freqs.keys())

        self.n_docs = len(self.doc_freqs)
        self.avgdl = (sum(self.doc_lens) / self.n_docs) if self.n_docs else 0.0
        self.idf = {
            term: math.log((self.n_docs - n + 0.5) / (n + 0.5) + 1.0)
            for term, n in df.items()
        }

    def get_scores(self, query: str) -> List[float]:
        q_terms = [t for t in tokenize(query) if t in self.idf]
        scores = [0.0] * self.n_docs
        if not q_terms or not self.avgdl:
            return scores
        for i, (freqs, dl) in enumerate(zip(self.doc_freqs, self.doc_lens)):
            norm = self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s = 0.0
            for t in q_terms:
                f = freqs.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            scores[i] = s
        return scores

    def top_k(self, query: str, k: int) -> List[Tuple[int, float]]:
        """Return [(doc_index, score)] for the k best documents with score > 0."""
        scores = self.get_scores(query)
        ranked = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
        return [(i, scores[i]) for i in ranked[:k] if scores[i] > 0]
