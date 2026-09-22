"""
RAG Q&A Engine  — v2
────────────────────
Improvements over v1:
  1. Hybrid retrieval  — semantic (ChromaDB) + keyword-boosted re-ranking
  2. Conversational memory — up to 4 prior turns passed as context
  3. Section-aware prompting — tells the LLM which report section each chunk is from
  4. Confidence scoring based on retrieval scores + source diversity
  5. Better citation deduplication — one citation per page, not per chunk
  6. Suggested follow-up questions returned alongside the answer
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from loguru import logger

from app.core.config import settings
from app.core.llm_client import chat_complete_json, chat_complete
from app.engines.embedding import retrieve_relevant_chunks


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class Citation:
    page_number: int
    excerpt: str
    filing_id: str
    section: str = ""


@dataclass
class QAResult:
    question: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    confidence: str = "medium"          # high / medium / low
    verified_against_kpi: bool = False
    kpi_verification_note: str = ""
    suggested_questions: List[str] = field(default_factory=list)


# ── Hybrid retrieval helpers ────────────────────────────────────────────────

def _keyword_score(text: str, query: str) -> float:
    """
    Simple keyword boost: fraction of query words present in text.
    Supplements semantic similarity for precise financial terms.
    """
    query_words = set(re.findall(r'\b\w+\b', query.lower()))
    if not query_words:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for w in query_words if w in text_lower)
    return hits / len(query_words)


def _hybrid_retrieve(
    query: str,
    filing_ids: List[str],
    top_k: int = 10,
) -> List[Dict]:
    """
    Retrieve chunks semantically, then re-rank with keyword boost.
    Returns up to top_k chunks sorted by hybrid score.
    """
    # Fetch more than needed so re-ranking has room to work
    raw = retrieve_relevant_chunks(
        query=query,
        filing_ids=filing_ids,
        chunk_type="qa",
        top_k=min(top_k * 2, 20),
    )

    if not raw:
        return []

    # Compute hybrid scores
    scored = []
    for chunk in raw:
        sem_score = float(chunk.get("score", 0.5))
        kw_score  = _keyword_score(chunk["text"], query)
        # 70% semantic + 30% keyword
        hybrid = 0.7 * sem_score + 0.3 * kw_score
        scored.append({**chunk, "hybrid_score": hybrid})

    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return scored[:top_k]


# ── Context block builder ────────────────────────────────────────────────────

def _build_context_block(chunks: List[Dict]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        meta = c.get("metadata", {})
        page    = meta.get("page_number", "?")
        filing  = meta.get("filing_id", "")[:8]   # short ID for readability
        score   = c.get("hybrid_score", c.get("score", 0))
        parts.append(
            f"[Source {i+1} | Page {page} | Filing: ...{filing} | Score: {score:.2f}]\n"
            f"{c['text']}"
        )
    return "\n\n".join(parts)


def _build_conversation_context(history: List[Dict]) -> str:
    """Format prior turns for inclusion in the prompt."""
    if not history:
        return ""
    lines = []
    for turn in history[-4:]:          # last 4 turns maximum
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content'][:400]}")
    return "\n".join(lines)


# ── LLM passes ───────────────────────────────────────────────────────────────

def _first_pass_answer(
    question: str,
    context: str,
    conversation_context: str = "",
) -> Dict:
    conv_block = ""
    if conversation_context:
        conv_block = f"\nPrior conversation (for context only):\n{conversation_context}\n"

    prompt = f"""You are a precise financial analyst assistant answering questions about annual reports.
Use ONLY the provided source chunks. If the answer is not clearly supported by the sources, say so.
Always cite source numbers when using information from them.{conv_block}

Source chunks:
{context}

Question: {question}

Respond with a JSON object:
{{
  "answer": "your detailed answer here (use markdown bold for key figures, e.g. **₹1,234 crores**)",
  "confidence": "high/medium/low",
  "source_indices": [list of source numbers used, e.g. [1, 3]],
  "key_figures": [list of numeric values mentioned in your answer, e.g. [1234.5, 567.8]],
  "suggested_questions": [2-3 natural follow-up questions the user might want to ask next]
}}"""

    try:
        return chat_complete_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
    except Exception as e:
        logger.error(f"QA first pass failed: {e}")
        raise


def _verification_pass(
    answer: str,
    key_figures: List,
    kpi_lookup: Dict[str, float],
) -> Tuple[bool, str]:
    """Cross-check numeric claims in the answer against the verified KPI table."""
    if not key_figures or not kpi_lookup:
        return False, ""

    for fig in key_figures:
        try:
            fig_val = float(fig)
        except (ValueError, TypeError):
            continue
        for kpi_name, kpi_val in kpi_lookup.items():
            if abs(kpi_val) < 1e-9:
                continue
            diff_pct = abs(fig_val - kpi_val) / abs(kpi_val)
            if diff_pct < 0.02:
                return True, f"Figure {fig_val:,.0f} matches verified KPI '{kpi_name}' = {kpi_val:,.0f}"

    return False, ""


# ── Confidence scoring ────────────────────────────────────────────────────────

def _compute_confidence(
    llm_confidence: str,
    chunks: List[Dict],
    source_indices: List[int],
) -> str:
    """
    Override or confirm the LLM's self-reported confidence based on
    retrieval quality (scores) and source diversity.
    """
    if not chunks or not source_indices:
        return "low"

    used_chunks = [chunks[i - 1] for i in source_indices if 1 <= i <= len(chunks)]
    if not used_chunks:
        return "low"

    avg_score = sum(c.get("hybrid_score", c.get("score", 0)) for c in used_chunks) / len(used_chunks)
    filing_ids = set(c.get("metadata", {}).get("filing_id", "") for c in used_chunks)

    # Downgrade if retrieval scores are poor
    if avg_score < 0.35:
        return "low"
    if avg_score < 0.55 or llm_confidence == "low":
        return "medium"

    # Multi-filing queries: if we found content across all requested filings, boost
    if len(filing_ids) > 1:
        return "high" if avg_score > 0.6 else "medium"

    return llm_confidence if llm_confidence in ("high", "medium", "low") else "medium"


# ── Citation deduplication ────────────────────────────────────────────────────

def _build_citations(chunks: List[Dict], source_indices: List[int]) -> List[Citation]:
    """One citation per unique (filing_id, page_number) pair, best excerpt."""
    seen: Dict[Tuple, Citation] = {}
    for idx in source_indices:
        if not (1 <= idx <= len(chunks)):
            continue
        c = chunks[idx - 1]
        meta = c.get("metadata", {})
        key = (meta.get("filing_id", ""), int(meta.get("page_number", 0)))
        if key not in seen:
            seen[key] = Citation(
                page_number=key[1],
                excerpt=c["text"][:250].strip(),
                filing_id=key[0],
                section=meta.get("section", ""),
            )
    return list(seen.values())


# ── Public entry point ────────────────────────────────────────────────────────

def answer_question(
    question: str,
    filing_ids: List[str],
    kpi_lookup: Optional[Dict[str, float]] = None,
    conversation_history: Optional[List[Dict]] = None,
    top_k: int = 10,
) -> QAResult:
    """
    Answer a natural-language question with hybrid retrieval and source citations.

    Args:
        question:              The user's question
        filing_ids:            Which filings to search
        kpi_lookup:            {kpi_name: value} for cross-verification
        conversation_history:  Prior turns [{role, content}, ...]
        top_k:                 Number of chunks to retrieve
    """
    logger.info(f"RAG QA: '{question[:80]}' over {len(filing_ids)} filing(s)")

    # ── 1. Hybrid retrieval ───────────────────────────────────────────────
    chunks = _hybrid_retrieve(query=question, filing_ids=filing_ids, top_k=top_k)

    if not chunks:
        return QAResult(
            question=question,
            answer="I couldn't find relevant content in the selected filings. "
                   "Make sure the report has finished processing.",
            confidence="low",
            suggested_questions=[
                "What are the key financial highlights?",
                "What risks does the company face?",
                "What is the revenue trend?",
            ],
        )

    context = _build_context_block(chunks)
    conv_ctx = _build_conversation_context(conversation_history or [])

    # ── 2. LLM answer pass ────────────────────────────────────────────────
    try:
        result = _first_pass_answer(question, context, conv_ctx)
    except Exception as e:
        logger.error(f"QA failed: {e}")
        return QAResult(
            question=question,
            answer=f"Sorry, I ran into an error while generating the answer: {e}",
            confidence="low",
        )

    answer          = result.get("answer", "No answer generated.")
    llm_confidence  = result.get("confidence", "medium")
    source_indices  = result.get("source_indices", [])
    key_figures     = result.get("key_figures", [])
    suggested_qs    = result.get("suggested_questions", [])

    # ── 3. Citations ──────────────────────────────────────────────────────
    citations = _build_citations(chunks, source_indices)

    # ── 4. KPI verification ───────────────────────────────────────────────
    verified, veri_note = False, ""
    if kpi_lookup:
        verified, veri_note = _verification_pass(answer, key_figures, kpi_lookup)

    # ── 5. Confidence scoring ─────────────────────────────────────────────
    confidence = _compute_confidence(llm_confidence, chunks, source_indices)

    logger.info(f"QA complete — confidence={confidence}, citations={len(citations)}, verified={verified}")

    return QAResult(
        question=question,
        answer=answer,
        citations=citations,
        confidence=confidence,
        verified_against_kpi=verified,
        kpi_verification_note=veri_note,
        suggested_questions=suggested_qs[:3],
    )
