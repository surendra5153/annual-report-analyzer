"""
Score cached Q&A runs per configuration (same metrics as notebook 05).

    python -m ml.eval.score_runs --set dev [--show-errors E_statement_pages]
"""
import argparse
import json

import pandas as pd

from ml.eval.rag_scoring import is_refusal, score_numeric, unsupported_figures
from ml.eval.run_rag_eval import SETS


def score(qset: str) -> pd.DataFrame:
    gold_path, runs_path = SETS[qset]
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in gold["questions"]}
    runs = [json.loads(l) for l in runs_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for r in {(r["config"], r["qid"]): r for r in runs}.values():
        q = qs[r["qid"]]
        unit = gold["filings"][q["filing"]]["unit"]
        src = "\n".join(s["text"] for s in r["sources"])
        row = {"config": r["config"], "qid": r["qid"], "kind": q["kind"], "answer": r["answer"],
               "latency_s": r["latency_s"], "cited": bool(r["cited"]),
               "fabricated": bool(unsupported_figures(r["answer"], src)), "refused": is_refusal(r["answer"])}
        if q["kind"] in ("amount", "per_share", "percent", "ratio"):
            row.update(score_numeric(r["answer"], q, unit))
        elif q["kind"] == "text":
            row["numeric_correct"] = row["unit_correct"] = any(a in r["answer"].lower() for a in q["accept"])
        rows.append(row)
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    ans, una = df[df.kind != "unanswerable"], df[df.kind == "unanswerable"]
    return pd.DataFrame({
        "n": ans.groupby("config").size(),
        "accuracy": ans.groupby("config").numeric_correct.mean(),
        "unit_acc": ans.groupby("config").unit_correct.mean(),
        "fabricated": df.groupby("config").fabricated.mean(),
        "refusal_acc": una.groupby("config").apply(lambda g: (g.refused & ~g.fabricated).mean()),
        "median_s": df.groupby("config").latency_s.median(),
    }).round(3)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--show-errors", default=None)
    a = ap.parse_args()
    d = score(a.set)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 160)
    print(summarise(d))
    if a.show_errors:
        e = d[(d.config == a.show_errors) & (d.kind != "unanswerable") & ~d.numeric_correct.astype(bool)]
        print(e[["qid", "answer"]].assign(answer=e.answer.str.replace("\n", " ").str.slice(0, 200)).to_string())
