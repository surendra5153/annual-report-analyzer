"""
Diagnostic tool to debug Q&A retrieval issues
Usage: python diagnose_qa.py "filing_id" "your question"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.engines.embedding import retrieve_relevant_chunks, get_filing_chunks
from app.ml.bm25 import BM25
from app.ml.fusion import reciprocal_rank_fusion
from app.ml.reranker import rerank_scores
from loguru import logger

def diagnose_retrieval(filing_id: str, question: str):
    print("=" * 80)
    print(f"🔍 DIAGNOSING Q&A RETRIEVAL")
    print("=" * 80)
    print(f"Filing ID: {filing_id}")
    print(f"Question: {question}")
    print("=" * 80)
    
    # 1. Check if chunks exist
    print("\n📦 STEP 1: Checking filing chunks...")
    corpus = get_filing_chunks([filing_id], chunk_type="qa")
    print(f"   Total chunks available: {len(corpus)}")
    if not corpus:
        print("   ❌ ERROR: No chunks found! Filing may not be processed yet.")
        return
    
    # Show sample chunks
    print(f"\n   Sample chunks (first 3):")
    for i, chunk in enumerate(corpus[:3]):
        text_preview = chunk['text'][:100].replace('\n', ' ')
        print(f"   [{i+1}] {text_preview}...")
    
    # 2. Dense retrieval (BGE embeddings)
    print(f"\n🔎 STEP 2: Dense retrieval (BGE embeddings)...")
    try:
        dense = retrieve_relevant_chunks(
            query=question,
            filing_ids=[filing_id],
            chunk_type="qa",
            top_k=10
        )
        print(f"   Retrieved: {len(dense)} chunks")
        print(f"\n   Top 3 results:")
        for i, chunk in enumerate(dense[:3]):
            score = chunk.get('score', 0)
            text_preview = chunk['text'][:100].replace('\n', ' ')
            print(f"   [{i+1}] Score: {score:.4f} | {text_preview}...")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        dense = []
    
    # 3. Sparse retrieval (BM25)
    print(f"\n📊 STEP 3: Sparse retrieval (BM25)...")
    try:
        bm25_index = BM25([c["text"] for c in corpus])
        sparse_results = bm25_index.top_k(question, 10)
        print(f"   Retrieved: {len(sparse_results)} chunks")
        print(f"\n   Top 3 results:")
        for i, (idx, score) in enumerate(sparse_results[:3]):
            text_preview = corpus[idx]['text'][:100].replace('\n', ' ')
            print(f"   [{i+1}] Score: {score:.4f} | {text_preview}...")
        sparse = [corpus[idx] for idx, _ in sparse_results]
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        sparse = []
    
    # 4. Fusion
    print(f"\n🔀 STEP 4: Reciprocal Rank Fusion...")
    by_id = {c["id"]: c for c in sparse}
    by_id.update({c["id"]: c for c in dense})
    
    if by_id:
        fused_ids = reciprocal_rank_fusion([
            [c["id"] for c in dense],
            [c["id"] for c in sparse]
        ])
        print(f"   Fused: {len(fused_ids)} unique chunks")
        candidates = [by_id[i] for i in fused_ids[:10]]
    else:
        print("   ⚠️  No chunks to fuse")
        candidates = []
    
    # 5. Reranking
    print(f"\n🎯 STEP 5: Cross-encoder reranking...")
    if settings.enable_reranker and candidates:
        try:
            probs = rerank_scores(question, [c["text"] for c in candidates])
            if probs is not None:
                scored = [{**c, "hybrid_score": p} for c, p in zip(candidates, probs)]
                scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
                print(f"   Reranked {len(scored)} chunks")
                print(f"\n   🏆 Top 3 after reranking:")
                for i, chunk in enumerate(scored[:3]):
                    score = chunk.get('hybrid_score', 0)
                    text_preview = chunk['text'][:100].replace('\n', ' ')
                    meta = chunk.get('metadata', {})
                    page = meta.get('page_number', '?')
                    print(f"   [{i+1}] Score: {score:.4f} | Page {page} | {text_preview}...")
                
                # Confidence assessment
                print(f"\n📊 CONFIDENCE ASSESSMENT:")
                avg_score = sum(c['hybrid_score'] for c in scored[:5]) / min(5, len(scored))
                print(f"   Average score (top 5): {avg_score:.4f}")
                if avg_score < 0.35:
                    print(f"   ⚠️  Score < 0.35 → Would result in LOW confidence")
                elif avg_score < 0.55:
                    print(f"   ⚠️  Score < 0.55 → Would result in MEDIUM confidence")
                else:
                    print(f"   ✅ Score ≥ 0.55 → Would result in HIGH confidence")
            else:
                print("   ⚠️  Reranker returned None, using RRF order")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    else:
        print("   ⚠️  Reranker disabled or no candidates")
    
    print("\n" + "=" * 80)
    print("💡 SUGGESTIONS:")
    print("=" * 80)
    if not corpus:
        print("• The filing hasn't been processed yet. Check processing status.")
    elif len(dense) == 0:
        print("• No semantic matches found. Try rephrasing the question.")
        print("• Check if the document contains content related to your question.")
    elif avg_score < 0.35:
        print("• Low retrieval scores indicate poor matches.")
        print("• Try more specific keywords that appear in the document.")
        print("• Check for spelling errors (e.g., 'stakeholder' not 'stake holder').")
    elif avg_score < 0.55:
        print("• Medium scores. The answer may be partial or uncertain.")
        print("• Try being more specific or using exact terms from the report.")
    else:
        print("• Retrieval looks good! If still getting low confidence, check LLM.")
    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python diagnose_qa.py <filing_id> <question>")
        print('Example: python diagnose_qa.py "abc-123-def" "What was the total revenue?"')
        sys.exit(1)
    
    filing_id = sys.argv[1]
    question = " ".join(sys.argv[2:])
    
    try:
        diagnose_retrieval(filing_id, question)
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
