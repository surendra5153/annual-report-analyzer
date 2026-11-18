"""
RAG Q&A Engine  — v2
────────────────────
Improvements over v1:
  1. Hybrid retrieval  — BM25 (sparse) + bge embeddings (dense), merged with
     Reciprocal Rank Fusion, then re-scored by a cross-encoder reranker
  2. Conversational memory — up to 4 prior turns passed as context
  3. Section-aware prompting — tells the LLM which report section each chunk is from
  4. Confidence scoring based on retrieval scores + source diversity
  5. Better citation deduplication — one citation per page, not per chunk
  6. Suggested follow-up questions returned alongside the answer
"""
import re
import time
from typing import Dict, Iterator, List, Optional, Tuple
from dataclasses import dataclass, field

from loguru import logger

from app.core.config import settings
from app.core.llm_client import chat_complete_json, chat_complete, chat_stream
from app.engines.embedding import retrieve_relevant_chunks, get_filing_chunks
from app.ml.bm25 import BM25
from app.ml.fusion import reciprocal_rank_fusion
from app.ml.reranker import rerank_scores
from app.ml.statement_index import retrieve_statement_pages


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


# ── Hybrid retrieval ────────────────────────────────────────────────────────

# BM25 indexes are built from the filing's stored chunks and cached briefly,
# since a chat session asks many questions against the same filings.
_BM25_CACHE: Dict[Tuple[str, ...], Tuple[float, BM25, List[Dict]]] = {}
_BM25_TTL_SECONDS = 600
_BM25_CACHE_MAX = 8


def _get_bm25(filing_ids: List[str]) -> Tuple[Optional[BM25], List[Dict]]:
    key = tuple(sorted(filing_ids))
    cached = _BM25_CACHE.get(key)
    if cached and time.time() - cached[0] < _BM25_TTL_SECONDS:
        return cached[1], cached[2]

    corpus = get_filing_chunks(filing_ids, chunk_type="qa")
    if not corpus:
        return None, []
    index = BM25([c["text"] for c in corpus])

    if len(_BM25_CACHE) >= _BM25_CACHE_MAX:
        _BM25_CACHE.pop(min(_BM25_CACHE, key=lambda k: _BM25_CACHE[k][0]))
    _BM25_CACHE[key] = (time.time(), index, corpus)
    return index, corpus


def _hybrid_retrieve(
    query: str,
    filing_ids: List[str],
    top_k: int = 10,
    mode: str = "hybrid",
) -> List[Dict]:
    """
    mode="dense" returns plain bge similarity search (the baseline compared in
    notebook 05); mode="hybrid" (default) runs the full pipeline:

    1. Dense: top-N chunks by bge cosine similarity (ChromaDB HNSW)
    2. Sparse: top-N chunks by BM25
    3. Reciprocal Rank Fusion of the two rankings
    4. Cross-encoder rerank of the fused candidates → top_k

    Each returned chunk carries `hybrid_score` in [0, 1] (reranker probability,
    or the dense score if the reranker is unavailable), used for confidence.
    """
    n = settings.retrieval_candidates

    dense = retrieve_relevant_chunks(query=query, filing_ids=filing_ids, chunk_type="qa", top_k=n)
    if mode == "dense":
        return [{**c, "hybrid_score": float(c.get("score", 0))} for c in dense[:top_k]]

    sparse: List[Dict] = []
    try:
        index, corpus = _get_bm25(filing_ids)
        if index is not None:
            sparse = [corpus[i] for i, _ in index.top_k(query, n)]
    except Exception as e:
        logger.warning(f"BM25 retrieval failed, using dense only: {e}")

    by_id: Dict[str, Dict] = {c["id"]: c for c in sparse}
    by_id.update({c["id"]: c for c in dense})  # dense entries carry a cosine score
    if not by_id:
        return []

    fused_ids = reciprocal_rank_fusion([[c["id"] for c in dense], [c["id"] for c in sparse]])
    candidates = [by_id[i] for i in fused_ids[:n]]

    probs = rerank_scores(query, [c["text"] for c in candidates])
    if probs is not None:
        scored = [{**c, "hybrid_score": p} for c, p in zip(candidates, probs)]
        scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    else:
        # No reranker: keep RRF order, use dense cosine (0.3 for sparse-only hits)
        scored = [{**c, "hybrid_score": float(c.get("score", 0.3))} for c in candidates]

    return scored[:top_k]


# ── Context block builder ────────────────────────────────────────────────────

def _build_context_block(chunks: List[Dict], filing_labels: Optional[Dict[str, str]] = None) -> str:
    """
    filing_labels: {filing_id: "Company · FY2026 · amounts in ₹ lakh"} — tells the
    model which report, year and unit each passage comes from, so it can state units.
    """
    parts = []
    for i, c in enumerate(chunks):
        meta = c.get("metadata", {})
        page    = meta.get("page_number", "?")
        fid     = meta.get("filing_id", "")
        report  = (filing_labels or {}).get(fid, f"Filing ...{fid[:8]}")
        # Short "[n]" handle first: models copy whatever header they see into the answer
        parts.append(f"Source [{i+1}] — {report} · page {page}\n{c['text']}")
    return "\n\n".join(parts)


_UNIT_RULES = (
    "Every monetary amount MUST be written with the rupee sign and its unit, e.g. **₹1,207.26 lakh**; "
    "take the unit from the source header ('amounts in ₹ …') unless the passage itself states another unit. "
    "Do not convert units yourself (the app adds exact ₹ crore equivalents). "
    "Prefer a line explicitly labelled with the asked item (e.g. 'Total Revenue') over figures from other tables. "
    "Tables often show two years side by side: give the figure for the report's fiscal year and name the year; "
    "mention the prior year only if it is clearly labelled. "
    "Never add up figures from different years or different tables."
)


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
    use_facts: bool = False,
) -> Dict:
    conv_block = ""
    if conversation_context:
        conv_block = f"\nPrior conversation (for context only):\n{conversation_context}\n"

    prompt = f"""You are a precise financial analyst assistant answering questions about annual reports.
Use ONLY the provided source chunks. If the answer is not clearly supported by the sources, say so.
Always cite source numbers when using information from them.
{_UNIT_RULES}{(" " + _FACTS_RULE) if use_facts else ""}{conv_block}

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
    filing_labels: Optional[Dict[str, str]] = None,
    kpi_facts: Optional[List[Dict]] = None,
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
    chunks = _with_kpi_facts(_hybrid_retrieve(query=question, filing_ids=filing_ids, top_k=top_k), kpi_facts)

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

    context = _build_context_block(chunks, filing_labels)
    conv_ctx = _build_conversation_context(conversation_history or [])

    # ── 2. LLM answer pass ────────────────────────────────────────────────
    try:
        result = _first_pass_answer(question, context, conv_ctx, use_facts=bool(kpi_facts))
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


# ── Streaming entry point (SSE chat) ──────────────────────────────────────────

# Matches [3], [Source 3], [1, 2], [Sources 1 and 4], [Source 1 | <report> | Page 36] — small models vary the format
_CITE_RE = re.compile(r"\[(?:sources?\s*)?(\d{1,2}(?:\s*(?:,|and|&)\s*\d{1,2})*)(?:\s*\|[^\]]*)?\]", re.IGNORECASE)


_BARE_CITE_RE = re.compile(r"(?<!\[)\bSource\s+(\d{1,2})\b")


def _cited_indices(text: str, n_sources: int) -> List[int]:
    found = {int(d) for group in _CITE_RE.findall(text) for d in re.findall(r"\d+", group)}
    found |= {int(n) for n in _BARE_CITE_RE.findall(text)}  # "Source 1" without brackets
    return sorted(i for i in found if 1 <= i <= n_sources)


_KPI_FACT_SCORE = 0.75  # retrieval-score stand-in for the verified KPI table (used by confidence)

_STATEMENT_RULE = (
    "Sources marked '— full page' are complete financial-statement pages: they are the most authoritative source. "
    "Copy figures digit-for-digit exactly as printed (do not add, drop or regroup digits) and use the unit stated "
    "in that page's header. "
    "Find the row whose label matches the question, read the column headers to pick the column of the asked year, "
    "and if such a page disagrees with the KPI table, use the statement page. For a percentage change, take both "
    "years from the same statement row and show the calculation."
)

_FACTS_RULE = (
    "Sources titled 'Extracted KPI table' list figures extracted from the financial statements; prefer them for "
    "headline figures (revenue, profit, assets, EPS, ratios) and for year-on-year changes. If a statement passage "
    "gives the exact item asked for with its scope (standalone / consolidated), use that passage and say which scope."
)


def system_prompt(kpi_facts: bool = False, statements: bool = False) -> str:
    """
    The Q&A system prompt. Single definition shared by the live engine and the
    fine-tuning data builder (ml/finetune/build_sft.py) so training matches serving.
    """
    return (
        "You are a precise financial analyst answering questions about annual reports. "
        "Use ONLY the provided sources. Cite sources inline only as [1], [2] right after the fact they support "
        "(never repeat the source title). "
        "Copy numbers exactly as written in the sources, with their years. "
        + _UNIT_RULES + " "
        + (_FACTS_RULE + " " if kpi_facts else "")
        + (_STATEMENT_RULE + " " if statements else "")
        + "If the sources do not contain the answer, say it is not found in the report. "
        "Use markdown bold for key figures."
    )


def _with_kpi_facts(chunks: List[Dict], kpi_facts: Optional[List[Dict]], last: bool = False) -> List[Dict]:
    """
    Add each filing's KPI table as a citable source — first (default) or last.
    Small models anchor on Source [1]; when full statement pages are present the
    (error-prone) KPI table goes last so the statements lead.
    """
    facts = [{
        "id": f"kpi-{f['filing_id']}",
        "text": f["text"],
        "metadata": {"filing_id": f["filing_id"], "page_number": f.get("page_number") or 0, "chunk_type": "kpi_table"},
        "hybrid_score": _KPI_FACT_SCORE,
    } for f in (kpi_facts or [])]
    return chunks + facts if last else facts + chunks


def _table_reader_answer(question: str, filing_id: str) -> Optional[List[Dict]]:
    """Events for a deterministic answer (app/ml/table_reader.py), or None to fall back to the LLM."""
    from app.db.database import SessionLocal
    from app.db.models import Filing
    from app.ml.statement_index import focus_text, statement_index
    from app.ml.table_reader import read, render_answer, source_excerpt

    db = SessionLocal()
    try:
        f = db.query(Filing).filter(Filing.id == filing_id).first()
        if not f or not f.file_path:
            return None
        try:
            res = read(question, f.id, f.file_path, f.fiscal_year)
        except Exception as e:  # never break chat on a parsing problem
            logger.warning(f"Table reader failed: {e}")
            return None
    finally:
        db.close()
    if not res.confident:
        logger.info(f"Table reader not confident ({res.reason}) → LLM")
        return None
    page_text = next((p["text"] for p in statement_index(filing_id) if p["page_number"] == res.page), "")
    source = {
        "index": 1, "kind": "statement_page", "page_number": res.page, "filing_id": filing_id,
        "excerpt": source_excerpt(res), "text": focus_text(page_text, question, 3500), "score": 1.0,
    }
    return [
        {"type": "sources", "sources": [source]},
        {"type": "token", "text": render_answer(res)},
        {"type": "done", "confidence": "high", "cited": [1], "mode": "table_reader"},
    ]


def stream_answer(
    question: str,
    filing_ids: List[str],
    conversation_history: Optional[List[Dict]] = None,
    top_k: int = 6,
    filing_labels: Optional[Dict[str, str]] = None,
    kpi_facts: Optional[List[Dict]] = None,
    retrieval: str = "hybrid",
    statement_pages: bool = False,
    model: Optional[str] = None,
    group_numbers: bool = True,
    facts_with_statements: bool = True,
    table_reader: bool = False,
) -> Iterator[Dict]:
    """
    Same retrieval as answer_question, but the answer is streamed as plain
    text with inline [n] source markers so the UI can render tokens live.

    kpi_facts: verified KPI tables (app/services/qa_context.kpi_facts) offered as
    extra sources; retrieval: "hybrid" (default) or "dense" (evaluation baseline).

    Yields events:
      {"type": "sources", "sources": [{index, kind, page_number, filing_id, excerpt, text, score}]}
      {"type": "token",   "text": "..."}
      {"type": "done",    "confidence": "...", "cited": [n, ...]}
    """
    # Whole statement pages for numeric questions (app/ml/statement_index.py); they replace two passages
    # Deterministic path: a confident statement-cell reading is answered without the LLM
    if table_reader and len(filing_ids) == 1:
        det = _table_reader_answer(question, filing_ids[0])
        if det is not None:
            yield from det
            return

    stmt = retrieve_statement_pages(question, filing_ids, k=2, group_numbers=group_numbers) if statement_pages else []
    passages = _hybrid_retrieve(query=question, filing_ids=filing_ids, top_k=top_k - (2 if stmt else 0), mode=retrieval)
    if stmt and not facts_with_statements:
        kpi_facts = None  # statement pages are authoritative; the extracted table only adds conflicting figures
    chunks = _with_kpi_facts(stmt + passages, kpi_facts, last=bool(stmt))
    yield {
        "type": "sources",
        "sources": [
            {
                "index": i + 1,
                "kind": {"kpi_table": "kpi_table", "statement_page": "statement_page"}.get(
                    c.get("metadata", {}).get("chunk_type"), "passage"),
                "page_number": int(c.get("metadata", {}).get("page_number", 0)),
                "filing_id": c.get("metadata", {}).get("filing_id", ""),
                "excerpt": c["text"][:250].strip(),
                "text": c["text"],  # full text: lets clients check that answer figures are grounded
                "score": round(float(c.get("hybrid_score", 0)), 3),
            }
            for i, c in enumerate(chunks)
        ],
    }

    if not chunks:
        yield {"type": "token", "text": "I couldn't find relevant content in the selected filings."}
        yield {"type": "done", "confidence": "low", "cited": []}
        return

    conv_ctx = _build_conversation_context(conversation_history or [])
    conv_block = f"\nPrior conversation (for context only):\n{conv_ctx}\n" if conv_ctx else ""
    messages = [
        {"role": "system", "content": system_prompt(kpi_facts=bool(kpi_facts), statements=bool(stmt))},
        {"role": "user", "content": f"{conv_block}\nSources:\n{_build_context_block(chunks, filing_labels)}\n\nQuestion: {question}"},
    ]

    answer_parts: List[str] = []
    for delta in chat_stream(messages, max_tokens=800, model=model):
        answer_parts.append(delta)
        yield {"type": "token", "text": delta}

    cited = _cited_indices("".join(answer_parts), len(chunks))
    yield {"type": "done", "confidence": _compute_confidence("medium", chunks, cited), "cited": cited}
