"""
Reader-only evaluation: how often is the deterministic table reader confident
(coverage), and how often is a confident answer correct (precision)?
No LLM involved — a pure algorithm metric.

    python -m ml.eval.reader_eval --set dev
"""
import argparse
import json
import os
import sys

from ml.eval.rag_scoring import _close
from ml.eval.run_rag_eval import SETS
from ml.paths import BACKEND_DIR


def evaluate(qset: str, verbose: bool = True):
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    from app.db.database import SessionLocal
    from app.db.models import Filing
    from app.ml.table_reader import read

    gold = json.loads(SETS[qset][0].read_text(encoding="utf-8"))
    db = SessionLocal()
    rows = []
    for q in gold["questions"]:
        f = db.query(Filing).filter(Filing.id == gold["filings"][q["filing"]]["id"]).first()
        res = read(q["question"], f.id, f.file_path, f.fiscal_year)
        correct = None
        if res.confident and q["kind"] in ("amount", "per_share"):
            correct = _close(res.value, q["value"], rel=0.005, abs_tol=0.01)
        elif res.confident and q["kind"] == "ratio":
            correct = False                      # the reader never computes ratios; confident here = wrong
        elif res.confident and q["kind"] == "percent":
            correct = res.change_pct is not None and _close(res.change_pct, q["value"], rel=0, abs_tol=q.get("tolerance", 0.3))
        elif res.confident:
            correct = False                      # confident on a text / unanswerable question = wrong
        rows.append({"qid": q["id"], "kind": q["kind"], "confident": res.confident, "correct": correct,
                     "value": res.value, "change": res.change_pct, "label": res.label, "page": res.page,
                     "reason": res.reason, "gold": q.get("value")})
        if verbose:
            mark = "—" if not res.confident else ("✓" if correct else "✗")
            print(f"{mark} {q['id']:4s} gold={q.get('value')!s:>11} got={res.value!s:>11} "
                  f"chg={(round(res.change_pct, 2) if res.change_pct is not None else '')!s:>7} "
                  f"p.{res.page} {res.label[:40]!r} {res.reason}")
    db.close()
    numeric = [r for r in rows if r["kind"] in ("amount", "per_share", "percent", "ratio")]
    conf = [r for r in numeric if r["confident"]]
    summary = {
        "questions": len(numeric),
        "coverage": len(conf) / len(numeric) if numeric else 0,
        "precision": sum(r["correct"] for r in conf) / len(conf) if conf else 0,
        "accuracy_if_reader_only": sum(bool(r["correct"]) for r in numeric) / len(numeric) if numeric else 0,
        "false_confident_on_unanswerable": sum(r["confident"] for r in rows if r["kind"] == "unanswerable"),
    }
    return rows, summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    a = ap.parse_args()
    _, s = evaluate(a.set)
    print(json.dumps(s, indent=1))
