"""
TAT-QA benchmark (Zhu et al., ACL 2021): hybrid tabular + textual financial QA
from real annual reports. Scored with the OFFICIAL metric (ml/data/tatqa/tatqa_metric.py):
exact match (EM) and numeracy-focused F1, scale-aware.

Setting: the question's own table + paragraphs are given (as in the paper; no retrieval).
Sample: a fixed, seeded 300-question stratified sample of the dev split (the official test
answers are hidden) — evaluation only, never used for tuning the Q&A system.

Configurations
  llm      local model (finsight-qwen = qwen2.5:3b, 8k context) answers in JSON {answer, scale}
  reader   deterministic table reader (single-row lookup / change / % change / average,
           computed in Python) when confident, else the llm answer

    python -m ml.eval.tatqa_eval --configs llm,reader [--n 300] [--score-only]
"""
import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

from ml.paths import BACKEND_DIR, DATA_DIR

TATQA_DIR = DATA_DIR / "tatqa"
RUNS = DATA_DIR / "tatqa_runs.jsonl"
SEED = 42


# ── Data ──────────────────────────────────────────────────────────────────────

def load_sample(n: int = 300) -> List[Tuple[dict, dict]]:
    docs = json.loads((TATQA_DIR / "tatqa_dataset_dev.json").read_text(encoding="utf-8"))
    pairs = [(d, q) for d in docs for q in d["questions"]]
    by_type: Dict[str, list] = {}
    for p in pairs:
        by_type.setdefault(p[1]["answer_type"], []).append(p)
    rng = random.Random(SEED)
    sample = []
    for _, items in sorted(by_type.items()):
        k = round(n * len(items) / len(pairs))
        sample += rng.sample(items, min(k, len(items)))
    return sample[:n]


def render_context(doc: dict) -> str:
    table = "\n".join(" | ".join(c.strip() for c in row) for row in doc["table"]["table"])
    paras = "\n".join(p["text"] for p in sorted(doc["paragraphs"], key=lambda p: p["order"]))
    return f"TABLE:\n{table}\n\nTEXT:\n{paras}"


# ── Deterministic reader for TAT-QA tables ────────────────────────────────────

_NUM = re.compile(r"^\(?-?\(?[\d,]*\.?\d+\)?%?$")
_SCALE_PATTERNS = [
    (re.compile(r"in (?:\$|€|£)?\s?thousands|\(thousands\)|(?:\$|€|£)\s?'?000s?\b|\('?000s?\)|\bin '?000s?\b", re.I), "thousand"),
    (re.compile(r"in (?:\$|€|£)?\s?millions|\(millions\)|\(in millions\)|(?:\$|€|£|us\$)\s?m\b|\(m\)|\bin m\b|\$\s?million", re.I), "million"),
    (re.compile(r"in (?:\$|€|£)?\s?billions|\(billions\)|(?:\$|€|£)\s?bn?\b", re.I), "billion"),
]
_OPS = [
    ("pct_change", re.compile(r"percent(?:age)? (?:change|increase|decrease)|% change|growth rate|percentage (?:growth|decline)", re.I)),
    ("average", re.compile(r"\baverage\b|\bmean\b", re.I)),
    ("change", re.compile(r"\bchange\b|\bdifference\b|\bincrease\b|\bdecrease\b", re.I)),
]
_MULTI_ROW = re.compile(
    r"\bratio\b|\bproportion\b|\bportion\b|\bpercentage of\b|\bshare of\b|\bconstitut|\bsum\b|\bcombined\b|"
    r"\btotal of\b|\bmore\b|\bless\b|\bthan\b|\bcompared\b|\bboth\b|\bexcluding\b|\bafter\b|\bhow many\b|"
    r"\bwhich\b|\bwhy\b|\bwhat (?:are|were) the\b", re.I)
_QSTOP = set("""what was were is are the of in for from to and between by did how much a an its
change changes changed difference increase decrease increased decreased percentage percent average mean
year years respectively during at as on fiscal fy""".split())


def _num(cell: str) -> Optional[float]:
    s = cell.strip().replace("$", "").replace("€", "").replace("£", "").replace(" ", "")
    if not s or s in {"-", "—", "–"} or not _NUM.match(s):
        return None
    neg = (s.startswith("(") and s.endswith(")")) or s.startswith("-")
    try:
        v = float(s.strip("()%").lstrip("-").replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


def doc_scale(doc: dict) -> Optional[str]:
    """Unit of the table's money values; None when ambiguous (several different units mentioned)."""
    text = " ".join(" ".join(r) for r in doc["table"]["table"][:4]) + " " + " ".join(p["text"] for p in doc["paragraphs"])
    found = {unit for rx, unit in _SCALE_PATTERNS if rx.search(text)}
    return found.pop() if len(found) == 1 else ("" if not found else None)


def _norm(s: str) -> List[str]:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def _content(words: List[str]) -> List[str]:
    return [w for w in words if w not in _QSTOP and not re.fullmatch(r"(19|20)\d{2}", w) and len(w) > 1]


def _year_columns(table: List[List[str]]) -> Dict[int, int]:
    cols: Dict[int, int] = {}
    for row in table[:4]:
        for j, cell in enumerate(row):
            m = re.search(r"\b(19|20)\d{2}\b", cell)
            if j > 0 and m and j not in cols:
                cols[j] = int(m.group(0))
    return cols


def reader_answer(doc: dict, q: dict) -> Optional[Tuple[str, str]]:
    """
    High-precision subset only: single-row lookup / change / % change / average over the
    table's year columns. Anything involving two rows, ratios, shares of a total or text
    is left to the LLM.
    """
    table = doc["table"]["table"]
    cols = _year_columns(table)
    question = q["question"]
    if not cols or _MULTI_ROW.search(question):
        return None
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", question)]
    rng = re.search(r"(\d+) years? from ((?:19|20)\d{2}) to ((?:19|20)\d{2})", question)
    if rng:
        years = list(range(int(rng.group(2)), int(rng.group(3)) + 1))
    if not years:
        return None
    op = next((name for name, rx in _OPS if rx.search(question)), "lookup")
    qcontent = _content(_norm(question))
    matches = []
    for row in table:
        label = row[0].strip()
        lw = _content(_norm(label))
        if lw and all(w in qcontent for w in lw):
            coverage = len(set(lw)) / max(len(set(qcontent)), 1)
            matches.append((coverage, len(lw), label, row))
    if not matches:
        return None
    matches.sort(key=lambda m: (-m[0], -m[1]))
    cov, _, label, row = matches[0]
    if cov < 0.75:
        return None                                        # question asks for more than this row
    if len(matches) > 1 and matches[1][0] == cov and matches[1][2] != label:
        return None                                        # two rows match equally well
    val, raw = {}, {}
    for j, y in cols.items():
        if j < len(row):
            v = _num(row[j])
            if v is not None:
                val[y], raw[y] = v, row[j].strip()
    scale = doc_scale(doc)
    if scale is None:
        return None
    ys = sorted(set(years))
    if any(y not in val for y in ys):
        return None
    is_pct_row = all("%" in raw[y] for y in ys)            # the values themselves are percentages
    if is_pct_row:
        scale = "percent"
    if op == "lookup":
        if len(ys) != 1:
            return None
        printed = raw[ys[0]].replace("$", "").replace("€", "").replace("£", "").replace("%", "").strip()
        return (printed, scale)                            # as printed, e.g. "(2,088)" — matches span answers
    if op == "average":
        return (f"{sum(val[y] for y in ys) / len(ys):.2f}", scale) if len(ys) >= 2 else None
    if len(ys) != 2:
        return None
    old, new = val[ys[0]], val[ys[1]]
    if op == "change" or (op == "pct_change" and is_pct_row):
        return (f"{new - old:.2f}", scale)                 # % change of a % row = difference in points
    if op == "pct_change" and old:
        return (f"{(new - old) / old * 100:.2f}", "percent")
    return None


# ── LLM ───────────────────────────────────────────────────────────────────────

_PROMPT = (
    "You answer questions about a company's financial report using ONLY the given table and text.\n"
    "Return a JSON object: {\"answer\": <string, number, or list of strings for several items>, "
    "\"scale\": one of \"\", \"thousand\", \"million\", \"billion\", \"percent\"}.\n"
    "- For values copied from the table, give the number as printed (without $ or commas) and the table's unit as scale.\n"
    "- For calculations (change, average, sum, percentage change), compute carefully and give the result rounded to 2 decimals.\n"
    "- Percentages: give the number (e.g. 12.5) with scale \"percent\".\n"
    "- For text answers copy the exact words from the text, scale \"\"."
)


def llm_answer(doc: dict, q: dict, model: str) -> Tuple[object, str]:
    from app.core.llm_client import chat_complete_json
    out = chat_complete_json([
        {"role": "system", "content": _PROMPT},
        {"role": "user", "content": f"{render_context(doc)}\n\nQUESTION: {q['question']}"},
    ], model=model, max_tokens=300)
    ans = out.get("answer", "") if isinstance(out, dict) else ""
    scale = out.get("scale", "") if isinstance(out, dict) else ""
    scale = scale if scale in {"", "thousand", "million", "billion", "percent"} else ""
    if isinstance(ans, (int, float)):
        ans = f"{ans}"
    return ans, scale


# ── Run + score ───────────────────────────────────────────────────────────────

def run(configs: List[str], n: int, model: str) -> None:
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    sample = load_sample(n)
    cached = {}
    if RUNS.exists():
        cached = {(r["config"], r["uid"]): r for r in map(json.loads, RUNS.read_text(encoding="utf-8").splitlines())}
    done = set(cached)
    with open(RUNS, "a", encoding="utf-8") as out:
        for cfg in configs:
            for i, (doc, q) in enumerate(sample):
                if (cfg, q["uid"]) in done:
                    continue
                t0, mode = time.time(), "llm"
                det = reader_answer(doc, q) if cfg == "reader" else None
                llm_row = cached.get(("llm", q["uid"]))
                if det:
                    ans, scale, mode = det[0], det[1], "reader"
                elif cfg == "reader" and llm_row:
                    # same model + prompt as the "llm" config: reuse its answer for the fallback
                    ans, scale = llm_row["answer"], llm_row["scale"]
                else:
                    try:
                        ans, scale = llm_answer(doc, q, model)
                    except Exception as e:
                        ans, scale = "", ""
                        print("LLM error", e)
                row = {"config": cfg, "uid": q["uid"], "answer": ans, "scale": scale, "mode": mode,
                       "latency_s": round(time.time() - t0, 2)}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                cached[(cfg, q["uid"])] = row
                if i % 25 == 0:
                    print(f"[{cfg}] {i}/{len(sample)}", flush=True)


def score(configs: List[str], n: int) -> dict:
    sys.path.insert(0, str(TATQA_DIR))
    from tatqa_metric import TaTQAEmAndF1  # official metric
    sample = load_sample(n)
    runs = {}
    for r in map(json.loads, RUNS.read_text(encoding="utf-8").splitlines()):
        runs[(r["config"], r["uid"])] = r
    results = {}
    for cfg in configs:
        metric = TaTQAEmAndF1()
        modes = Counter()
        by_type: Dict[str, List[float]] = {}
        for _, q in sample:
            r = runs.get((cfg, q["uid"]))
            if r is None:
                continue
            modes[r["mode"]] += 1
            before = metric._total_em
            metric(ground_truth=q, prediction=r["answer"], pred_scale=r["scale"])
            by_type.setdefault(q["answer_type"], []).append(metric._total_em - before)
        em, f1, scale_acc, _ = metric.get_overall_metric()
        results[cfg] = {"n": sum(modes.values()), "em": round(em * 100, 2), "f1": round(f1 * 100, 2),
                        "scale_acc": round(scale_acc * 100, 2), "modes": dict(modes),
                        "em_by_type": {t: round(100 * sum(v) / len(v), 1) for t, v in sorted(by_type.items())}}
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="llm,reader")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--model", default="finsight-qwen")
    ap.add_argument("--score-only", action="store_true")
    a = ap.parse_args()
    cfgs = a.configs.split(",")
    if not a.score_only:
        run(cfgs, a.n, a.model)
    print(json.dumps(score(cfgs, a.n), indent=1))
