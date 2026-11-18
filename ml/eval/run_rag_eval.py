"""
Run the Q&A gold set (rag_gold.json) through each configuration and cache the
raw outputs to ml/data/rag_eval_runs.jsonl. Resumable: (config, question) pairs
already in the cache are skipped, so the expensive LLM calls run once.

Configurations (rubric item 3 — compared in notebook 05):
  A_dense          bge dense retrieval only
  B_hybrid         BM25 + dense → RRF → cross-encoder rerank
  C_hybrid_facts   B + the KPI table, verified rows only, as an extra source
  D_hybrid_all_kpis B + every KPI that survived cleansing (unchecked rows marked)
  E_statement_pages D + whole financial-statement pages for numeric questions (8k-context model)
  F_statement_v2    E + row-focused page windows, page-level unit headers, KPI table placed last,
                    printed-unit-first KPI values, digit-copy rule (same parameters; engine v2)
  G_grouped_numbers F + Indian digit grouping of long ungrouped figures on statement pages
  H_statements_no_kpi G, but the KPI table is dropped when statement pages were retrieved
  J_table_reader    H + deterministic table reader: confident statement-cell lookups answered without the LLM

Usage (from repo root, with Ollama running):
    python -m ml.eval.run_rag_eval [--configs A_dense,B_hybrid,C_hybrid_facts] [--limit N]
"""
import argparse
import json
import os
import sys
import time

from ml.paths import BACKEND_DIR, DATA_DIR, ML_DIR

CONFIGS = {
    "A_dense": {"retrieval": "dense", "facts": False},
    "B_hybrid": {"retrieval": "hybrid", "facts": False},
    "C_hybrid_facts": {"retrieval": "hybrid", "facts": "verified"},
    "D_hybrid_all_kpis": {"retrieval": "hybrid", "facts": "all"},
    "E_statement_pages": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsight-qwen"},
    "F_statement_v2": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsight-qwen",
                       "group_numbers": False},
    "G_grouped_numbers": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsight-qwen"},
    "H_statements_no_kpi": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsight-qwen",
                            "facts_with_statements": False},
    "J_table_reader": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsight-qwen",
                       "facts_with_statements": False, "table_reader": True},
    # After fine-tuning (ml/FINETUNING.md): identical to J, but the LLM fallback is our FinSumm model
    "K_finsumm": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsumm",
                  "facts_with_statements": False, "table_reader": True},
    # Isolates the fine-tune itself: H with FinSumm (every answer goes through the LLM)
    "H_finsumm": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsumm",
                  "facts_with_statements": False},
    # FinSumm v2: labels copy figures verbatim, past-year refusals, paraphrases + company names, ratios
    "K_finsumm2": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsumm2",
                   "facts_with_statements": False, "table_reader": True},
    "H_finsumm2": {"retrieval": "hybrid", "facts": "all", "statement_pages": True, "model": "finsumm2",
                   "facts_with_statements": False},
}
SETS = {  # dev: tune on it freely · test: score once per finished configuration
    "test": (ML_DIR / "eval" / "rag_gold.json", DATA_DIR / "rag_eval_runs.jsonl"),
    "dev": (ML_DIR / "eval" / "rag_dev.json", DATA_DIR / "rag_dev_runs.jsonl"),
    "test2": (ML_DIR / "eval" / "rag_gold_v2.json", DATA_DIR / "rag_test2_runs.jsonl"),   # harder, frozen
}
GOLD_PATH, RUNS_PATH = SETS["test"]


def load_cache(runs_path=RUNS_PATH) -> dict:
    if not runs_path.exists():
        return {}
    rows = [json.loads(l) for l in runs_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {(r["config"], r["qid"]): r for r in rows}


def main(configs, limit=None, qset="test"):
    gold_path, runs_path = SETS[qset]
    # The backend resolves its DB / vector-store paths relative to backend/
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    from app.db.database import SessionLocal
    from app.engines.rag_qa import stream_answer
    from app.services.qa_context import filing_labels, kpi_facts

    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    questions = gold["questions"][:limit] if limit else gold["questions"]
    cache = load_cache(runs_path)
    db = SessionLocal()

    with open(runs_path, "a", encoding="utf-8") as out:
        for cfg_name in configs:
            cfg = CONFIGS[cfg_name]
            for q in questions:
                if (cfg_name, q["id"]) in cache:
                    continue
                fid = gold["filings"][q["filing"]]["id"]
                labels = filing_labels(db, [fid])
                facts = kpi_facts(db, [fid], verified_only=cfg["facts"] == "verified") if cfg["facts"] else None
                t0, first = time.time(), None
                answer, sources, done = "", [], {}
                for e in stream_answer(q["question"], [fid], filing_labels=labels, kpi_facts=facts,
                                       retrieval=cfg["retrieval"], statement_pages=cfg.get("statement_pages", False),
                                       model=cfg.get("model"), group_numbers=cfg.get("group_numbers", True),
                                       facts_with_statements=cfg.get("facts_with_statements", True),
                                       table_reader=cfg.get("table_reader", False)):
                    if e["type"] == "sources":
                        sources = e["sources"]
                    elif e["type"] == "token":
                        first = first or time.time()
                        answer += e["text"]
                    elif e["type"] == "done":
                        done = e
                row = {
                    "config": cfg_name, "qid": q["id"], "question": q["question"], "answer": answer,
                    "cited": done.get("cited", []), "confidence": done.get("confidence"), "mode": done.get("mode", "llm"),
                    "sources": [{k: s[k] for k in ("index", "kind", "page_number", "text", "score")} for s in sources],
                    "latency_s": round(time.time() - t0, 2),
                    "first_token_s": round((first or time.time()) - t0, 2),
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[{cfg_name}] {q['id']} {row['latency_s']:>5.1f}s  {answer[:90]!r}", flush=True)
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--set", choices=list(SETS), default="test")
    a = ap.parse_args()
    main(a.configs.split(","), a.limit, a.set)
