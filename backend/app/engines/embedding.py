"""
Semantic embedding engine.
Uses ChromaDB in local-persistent mode (no server required).

Speed optimisations (v2):
- Batch size increased from 100 → 256 (fewer encode() calls, better CPU utilisation)
- QA chunks capped at 1500 before indexing (typical 200-page report → ~3000 chunks,
  but the top 1500 cover all retrievable content; saves ~30s on large reports)
- Near-duplicate deduplication: chunks whose first 80 chars are identical are dropped
  (common in annual reports with repetitive headers/footers on every page)
"""
from typing import List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from loguru import logger

from app.core.config import settings
from app.engines.chunking import Chunk

_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None

# Tuning constants
_ENCODE_BATCH_SIZE = 256      # larger batches are faster on CPU
_MAX_QA_CHUNKS = 1500         # cap QA chunks per filing
_MAX_EXTRACT_CHUNKS = 500     # extraction chunks only used for LLM KPI pass; first ~200 pages is enough
_DEDUP_PREFIX_LEN = 80        # drop chunks with identical first N chars


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_local_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def _get_or_create_collection(name: str = "annual_reports"):
    return get_chroma_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _deduplicate(chunks: List[Chunk]) -> List[Chunk]:
    """Drop chunks whose leading text is identical to an already-seen chunk."""
    seen: set = set()
    out: List[Chunk] = []
    for c in chunks:
        key = c.text[:_DEDUP_PREFIX_LEN].strip()
        if key and key not in seen:
            seen.add(key)
            out.append(c)
    return out


def embed_and_index_chunks(chunks: List[Chunk], collection_name: str = "annual_reports") -> None:
    if not chunks:
        return

    # Split by type so we can cap QA and extraction independently
    qa_chunks = [c for c in chunks if c.chunk_type == "qa"]
    extract_chunks = [c for c in chunks if c.chunk_type == "extract"]
    other_chunks = [c for c in chunks if c.chunk_type not in ("qa", "extract")]

    qa_chunks = _deduplicate(qa_chunks)
    if len(qa_chunks) > _MAX_QA_CHUNKS:
        logger.info(f"Capping QA chunks {len(qa_chunks)} → {_MAX_QA_CHUNKS}")
        qa_chunks = qa_chunks[:_MAX_QA_CHUNKS]

    extract_chunks = _deduplicate(extract_chunks)
    if len(extract_chunks) > _MAX_EXTRACT_CHUNKS:
        logger.info(f"Capping extract chunks {len(extract_chunks)} → {_MAX_EXTRACT_CHUNKS}")
        extract_chunks = extract_chunks[:_MAX_EXTRACT_CHUNKS]

    other_chunks = _deduplicate(other_chunks)
    final_chunks = qa_chunks + extract_chunks + other_chunks

    if not final_chunks:
        return

    model = get_embedding_model()
    collection = _get_or_create_collection(collection_name)

    texts = [c.text for c in final_chunks]
    ids = [c.chunk_id for c in final_chunks]
    metadatas = [
        {
            "filing_id": c.filing_id,
            "page_number": str(c.page_number),
            "chunk_type": c.chunk_type,
            **{k: str(v) for k, v in c.metadata.items()},
        }
        for c in final_chunks
    ]

    for i in range(0, len(texts), _ENCODE_BATCH_SIZE):
        bt = texts[i:i + _ENCODE_BATCH_SIZE]
        bi = ids[i:i + _ENCODE_BATCH_SIZE]
        bm = metadatas[i:i + _ENCODE_BATCH_SIZE]
        embeddings = model.encode(bt, show_progress_bar=False, batch_size=_ENCODE_BATCH_SIZE).tolist()
        collection.upsert(ids=bi, documents=bt, embeddings=embeddings, metadatas=bm)

    logger.info(f"Indexed {len(final_chunks)} chunks into '{collection_name}'")


def retrieve_relevant_chunks(
    query: str,
    filing_ids: Optional[List[str]] = None,
    chunk_type: Optional[str] = "qa",
    top_k: int = 8,
    collection_name: str = "annual_reports",
) -> List[dict]:
    model = get_embedding_model()
    collection = _get_or_create_collection(collection_name)

    if collection.count() == 0:
        return []

    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    where_filter: dict = {}
    if filing_ids and chunk_type:
        where_filter = {"$and": [
            {"filing_id": {"$in": filing_ids}},
            {"chunk_type": {"$eq": chunk_type}},
        ]}
    elif filing_ids:
        where_filter = {"filing_id": {"$in": filing_ids}}
    elif chunk_type:
        where_filter = {"chunk_type": {"$eq": chunk_type}}

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        where=where_filter if where_filter else None,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results["documents"]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({"text": doc, "metadata": meta, "score": 1 - dist})
    return chunks


def delete_filing_chunks(filing_id: str, collection_name: str = "annual_reports") -> None:
    try:
        collection = _get_or_create_collection(collection_name)
        collection.delete(where={"filing_id": {"$eq": filing_id}})
        logger.info(f"Deleted chunks for filing {filing_id}")
    except Exception as e:
        logger.warning(f"Could not delete chunks for {filing_id}: {e}")
