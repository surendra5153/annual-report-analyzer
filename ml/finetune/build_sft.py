"""
Build FinSumm supervised fine-tuning (SFT) data from the TRAINING reports
(ml/data/train_pdfs/manifest.csv — evaluation companies are excluded at collection).

Every example uses the production format exactly:
  * system prompt  = app.engines.rag_qa.system_prompt(statements=True)
  * sources        = whole statement pages from app.ml.statement_index.retrieve_statement_pages
                     (+ narrative distractor passages), rendered by rag_qa._build_context_block
  * answer         = written from the deterministic table reader's cell values, so every
                     number in a label is exact (no LLM teacher needed for these types)

Example types (targets per report are capped so no company dominates):
  lookup         current-year value of a statement row          "The consolidated finance costs for FY 2024-25 were **₹5,978.02 crore** [2]."
  prior_year     the comparative column                         (teaches reading the year header)
  change         % change computed in Python                    (teaches showing both years + the result)
  scope          standalone vs consolidated pages both present  (hard negative)
  unanswerable   item / year not in the sources                 "… is not found in the report."

Split by COMPANY (95 / 5) into ml/data/sft/sft_train.jsonl and sft_val.jsonl.

    python -m ml.finetune.build_sft                    # all training reports
    python -m ml.finetune.build_sft --smoke            # 15 examples from one app report → smoke.jsonl
                                                       # (format check only — never train on it)
"""
import argparse
import csv
import json
import os
import random
import re
import sys
from pathlib import Path

from ml.paths import BACKEND_DIR, DATA_DIR

SFT_DIR = DATA_DIR / "sft"
TRAIN_DIR = DATA_DIR / "train_pdfs"
SEED = 13
PER_REPORT = 120
SKIP_LABEL = re.compile(r"^(total|less|add|particulars|notes?|income|expenses|assets|liabilities|equity|"
                        r"continuing operations|discontinued operations)$", re.I)
FAKE_ITEMS = ["revenue from the Mars mining division", "Bitcoin holdings", "number of retail stores in Antarctica",
              "royalty income from space tourism", "carbon credits sold to the Moon base", "revenue from electric aircraft sales"]


def _backend():
    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))


_ENUM = re.compile(r"^(?:\(?[a-z]{1,4}\)|\(?[ivxl]+\)|\d+\.|[a-z]\.)\s+", re.I)
_NOTE_REF = re.compile(r"\s+\d+[A-Z]?(?:\s*\([a-z]\))?(?:\s*(?:&|,)\s*\d+[A-Z]?)*$")


def clean_label(label: str) -> str:
    """'(l) Other non-current assets' → 'Other non-current assets'; 'Total (i) Financial Assets' → 'Total Financial Assets'."""
    s = re.sub(r"\s*\.{2,}[\s.]*", " ", label)                                     # dot leaders: "Lease liabilities……"
    s = re.sub(r"\s+", " ", s).strip(" :-")
    for _ in range(3):
        s = _ENUM.sub("", s)
    s = re.sub(r"\b(total)\s+\(?[ivxl]+\)\s+", r"\1 ", s, flags=re.I)
    s = re.sub(r"\s*\(\s*[a-z](?:\s*[+-]\s*[a-z])+\s*\)", "", s, flags=re.I)     # "(a + b + c)", "(I+II)"
    s = re.sub(r"\s*\(\s*(?:\d+\s*)?[a-z₹]\s*\)$", "", s, flags=re.I)               # trailing "(j)", "(J)" = ₹ glyph, "18 (5)"
    s = re.sub(r"\s*\((?:in\s+)?[₹`]\)", "", s)                                     # "Basic (in `)", "EPS (₹)"
    s = _NOTE_REF.sub("", s).strip(" :-#*")
    s = re.sub(r"\s+[a-z]$", "", s)                                                # footnote letter: "…activities b"
    s = re.sub(r"^(?:consolidated|standalone)\s+", "", s, flags=re.I)              # scope goes in the question
    s = re.sub(r"\b(\w+) \1\b", r"\1", s, flags=re.I)                              # "Total total comprehensive…"
    return s.strip(" :-#*")


# Rows that are not usable as standalone questions: wrapped/merged labels, footnote markers, schedule
# movements, counts and ratios (they are not ₹ amounts).
_NOISY_LABEL = re.compile(
    r"\d|\[|\+|%|¢|`|\brefer\b|^(?:less|add|of which|in)\b|\b(?:for|of|to|and|attributable to|the|in|on|from|by|at|as|per)$|"
    r"(?<!per )(?<!equity )\bshare$|^(?:equity holders|owners|shareholders) of\b|"
    r"\b(?:carried (?:forward|over)|brought forward|opening balance|closing balance|additions during|"
    r"deductions during|number of|no\.|ratio|level)\b", re.I)
_GENERIC_LABEL = re.compile(r"^(?:net|others?|basic|diluted|billed|unbilled|shares|secured|unsecured|"
                            r"in current accounts|in other deposit accounts|current|non-current|non-controlling interests?)$", re.I)
_PER_SHARE = re.compile(r"per (?:equity )?share|\beps\b", re.I)
# Cash-flow rows worth asking about are cash movements; the "adjustments" block repeats P&L names with
# flipped signs ("Dividend income  (130)"), which would teach a wrong answer to "what was the dividend income?"
_CASH_MOVEMENT = re.compile(r"paid|received|proceeds|payments?|purchase|repayment|net cash|activities|increase|decrease|"
                            r"cash and cash|acquisition|sale of|redemption|investment in|loans? given|deposits", re.I)


def usable_label(label: str, kind: str = "") -> bool:
    return (len(label) >= 4 and label.count("(") == label.count(")") and not SKIP_LABEL.match(label)
            and not _GENERIC_LABEL.match(label) and not _NOISY_LABEL.search(label)
            and (kind != "cash_flow" or bool(_CASH_MOVEMENT.search(label))))


def _verb(label: str) -> str:
    last = label.split()[-1].lower() if label.split() else ""
    return "were" if last.endswith("s") and not last.endswith(("ss", "ness", "us")) else "was"


def _fy(y: int) -> str:
    return f"FY {y - 1}-{str(y)[2:]}"


def _printed(raw: str, v: float, unit: str) -> str:
    """
    The figure copied EXACTLY as the model sees it in the source (the printed digits, after the same
    digit grouping the app applies) — FinSumm v1 was trained on reformatted figures and learned to
    re-type digits, which a 3B model gets wrong. Only the sign is normalised: "(1,116.49)" → "-₹1,116.49".
    """
    from app.ml.statement_index import group_digits
    digits = group_digits(raw.replace("₹", "").strip().strip("()").lstrip("-"))
    sign = "-" if v < 0 else ""
    return f"{sign}₹{digits} per share" if unit == "per_share" else f"{sign}₹{digits} {unit}"


def _short_name(company: str) -> str:
    """'Tata Consultancy Services Ltd.' → 'Tata Consultancy Services'."""
    return re.sub(r"\s+(?:Ltd\.?|Limited|Corporation of India Ltd\.?)$", "", company).strip()


# How people actually ask (test v1 showed the model must map these onto statement rows)
PARAPHRASES = {
    "employee benefits expense": ["spend on its employees", "employee costs", "staff costs"],
    "employee benefit expenses": ["spend on its employees", "employee costs"],
    "employee benefits expenses": ["spend on its employees", "employee costs"],
    "finance costs": ["interest cost", "borrowing costs"],
    "revenue from operations": ["revenue", "sales", "turnover"],
    "profit for the year": ["net profit", "profit after tax", "PAT"],
    "profit before tax": ["PBT", "pre-tax profit"],
    "depreciation and amortisation expense": ["depreciation charge", "depreciation and amortisation"],
    "depreciation and amortization expense": ["depreciation charge", "depreciation and amortization"],
    "cash and cash equivalents": ["cash and cash equivalents", "cash balance"],
    "inventories": ["inventory", "stock"],
    "trade receivables": ["receivables", "amounts owed by customers"],
    "other income": ["non-operating income"],
    "total income": ["total income", "total revenue"],
}
_PARA_FORMS = [
    "What was {co}'s {sc}{p} {period}?",
    "How much did {co} report as {sc}{p} {period}?",
    "What was {co}'s {p} {period}{basis}?",
]


def _distractors(page_texts, statement_pages, rng, k=3):
    others = [i for i in range(len(page_texts)) if (i + 1) not in statement_pages and len(page_texts[i]) > 600]
    out = []
    for i in rng.sample(others, min(k, len(others))):
        start = rng.randrange(0, max(1, len(page_texts[i]) - 400))
        out.append({"text": page_texts[i][start:start + 400], "metadata": {"page_number": i + 1}})
    return out


def _example(question, chunks, key, label, answer, kind):
    from app.engines.rag_qa import _build_context_block, system_prompt
    for c in chunks:
        c["metadata"]["filing_id"] = key
    user = f"\nSources:\n{_build_context_block(chunks, {key: label})}\n\nQuestion: {question}"
    return {"type": kind, "messages": [
        {"role": "system", "content": system_prompt(statements=True)},
        {"role": "user", "content": user},
        {"role": "assistant", "content": answer},
    ]}


def content_kind(labels) -> str:
    """
    Statement type from the rows, for pages without a textual heading (Wipro prints it as an image).
    Only a page that unmistakably is one primary statement gets a type; anything else stays "statement".
    """
    ls = [l.lower() for l in labels]
    has = lambda *keys: any(all(k in l for k in keys) for l in ls)
    pl = (has("total income") or has("revenue from operations")) and has("profit", "before tax") and has("expenses")
    bs = has("total assets") and (has("total equity") or has("equity and liabilities"))
    cf = has("operating activities") and has("investing activities")
    kinds = [k for k, ok in (("profit_loss", pl), ("balance_sheet", bs), ("cash_flow", cf)) if ok]
    return kinds[0] if len(kinds) == 1 else "statement"


def build_report(pdf: Path, company: str, fy: int, rng: random.Random, cap: int = PER_REPORT) -> list:
    import fitz
    from app.ml.kpi_clean import detect_report_unit_with_fallback
    from app.ml.statement_index import retrieve_statement_pages, statement_index
    from app.ml.table_reader import read_tables
    from app.ml.text_clean import normalize_unicode

    key = "train-" + pdf.stem
    pages = statement_index(key, str(pdf))
    if not pages:
        return []
    with fitz.open(pdf) as d:
        page_texts = [normalize_unicode(p.get_text()) for p in d]
    unit, _, _ = detect_report_unit_with_fallback([p["text"] for p in pages], page_texts)
    label = f"{company} · FY{fy} · amounts in ₹ {unit}"
    stmt_pages = {p["page_number"] for p in pages}
    has_cons = any(p["scope"] == "consolidated" for p in pages)  # unlabelled statements are then standalone

    rows = []   # (scope, kind, row_label, values, years, unit)
    for p in pages:
        if p["kind"] not in ("profit_loss", "balance_sheet", "cash_flow", "statement"):
            continue
        for t in read_tables(str(pdf), p["page_number"], p["scope"], p["kind"]):
            t_kind = t.kind if t.kind != "statement" else content_kind(r.label for r in t.rows)
            if t_kind not in ("profit_loss", "balance_sheet", "cash_flow"):
                continue
            # Each table's own unit declaration wins (banks: standalone in ₹ '000, consolidated in ₹ crore)
            t_unit = t.unit or unit
            if not 2 <= len(t.years) <= 3:          # 5/10-year highlights pages are not statements
                continue
            counts = {}
            for r in t.rows:
                counts[clean_label(r.label).lower()] = counts.get(clean_label(r.label).lower(), 0) + 1
            for r in t.rows:
                lab = clean_label(r.label)
                if not usable_label(lab, t_kind) or counts[lab.lower()] > 1 or not all(y in r.values for y in sorted(t.years, reverse=True)[:2]):
                    continue                        # ambiguous: the same label under two sections (current / non-current)
                if not all(y in r.raw for y in sorted(t.years, reverse=True)[:2]):
                    continue
                rows.append((t.scope, t_kind, lab, r.values, t.years, "per_share" if _PER_SHARE.search(lab) else t_unit, r.raw))
    # "Interest income" is a P&L line and also a (negative) cash-flow adjustment: one question, one answer —
    # the P&L / balance-sheet row wins
    primary = {(r[0], r[2].lower()) for r in rows if r[1] != "cash_flow"}
    rows = [r for r in rows if r[1] != "cash_flow" or (r[0], r[2].lower()) not in primary]
    rng.shuffle(rows)

    co = _short_name(company)
    out, seen = [], set()
    for scope, kind, lab, values, years, unit, raw in rows:
        if len(out) >= cap:
            break
        if (scope, lab.lower()) in seen:
            continue
        seen.add((scope, lab.lower()))
        cur, prev = sorted(years, reverse=True)[:2]          # IFRS sections print the older year first
        scope = scope if scope != "unknown" else ("standalone" if has_cons else "unknown")
        sc = f"{scope} " if scope in ("consolidated", "standalone") else ""
        bs = kind == "balance_sheet"
        period = (lambda y: f"as at 31 March {y}") if bs else (lambda y: f"for {_fy(y)}")
        roll = rng.random()
        paras = PARAPHRASES.get(re.sub(r"\s*\((?:net)\)$", "", lab.lower()))
        if roll < (0.6 if paras else 0.25):
            # natural phrasing + company name: "How much did Titan spend on its employees in FY 2025-26 (consolidated)?"
            kind_ex, year = "paraphrase", rng.choice([cur, cur, prev])
            p = rng.choice(paras) if paras else lab.lower()
            basis = rng.choice([f" ({scope})", f" on a {scope} basis"]) if sc else ""
            per = f"as at 31 March {year}" if bs else rng.choice([f"in {_fy(year)}", f"for {_fy(year)}"])
            q = (f"How much did {co} spend on its employees {per}{basis}?" if p == "spend on its employees"
                 else rng.choice(_PARA_FORMS).format(co=co, sc=sc, p=p, period=per, basis=basis))
        elif roll < 0.55:
            kind_ex, year = "lookup", cur
            q = rng.choice([f"What was the {sc}{lab.lower()} {period(year)}?",
                            f"How much was the {sc}{lab.lower()} {period(year)}?",
                            f"What did the company report as {sc}{lab.lower()} {period(year)}?"])
        elif roll < 0.75:
            kind_ex, year = "prior_year", prev
            q = f"What was the {sc}{lab.lower()} {period(year)}?"
        else:
            kind_ex, year = "change", cur
            q = rng.choice([f"By what percentage did the {sc}{lab.lower()} change in {_fy(cur)} compared with {_fy(prev)}?",
                            f"How did the {sc}{lab.lower()} change from {_fy(prev)} to {_fy(cur)}?"])
        chunks = retrieve_statement_pages(q, [key], k=2)
        if not chunks:
            continue
        # the answer must be visible: a source counts only if it shows the row AND the exact figures
        # (otherwise the retrieved page is the wrong one, or the row fell outside the page excerpt)
        need = [_printed(raw[y], values[y], "x").split("₹")[1][:-2] for y in ((cur, prev) if kind_ex == "change" else (year,))]
        idx = next((i for i, c in enumerate(chunks)
                    if lab.split()[0].lower() in c["text"].lower() and all(d in c["text"] for d in need)), None)
        if idx is None:
            continue
        chunks = chunks + _distractors(page_texts, stmt_pages, rng)
        order = list(range(len(chunks)))
        rng.shuffle(order)
        chunks = [chunks[i] for i in order]
        n = order.index(idx) + 1
        if kind_ex == "change":
            # % change is meaningless across a sign flip or from a near-zero base
            if not values[prev] or values[prev] * values[cur] <= 0 or abs(values[prev]) < 1:
                continue
            pct = (values[cur] - values[prev]) / abs(values[prev]) * 100
            ans = (f"The {sc}{lab.lower()} {_verb(lab)} **{_printed(raw[cur], values[cur], unit)}** {period(cur)}, compared with "
                   f"{_printed(raw[prev], values[prev], unit)} {period(prev)} — a change of **{pct:+.2f}%** [{n}].")
        else:
            ans = f"The {sc}{lab.lower()} {period(year)} {_verb(lab)} **{_printed(raw[year], values[year], unit)}** [{n}]."
        out.append(_example(q, chunks, key, label, ans, "scope" if sc and kind_ex == "lookup" and rng.random() < 0.3 else kind_ex))

    out += _ratio_examples(rows, co, key, label, page_texts, stmt_pages, rng, has_cons)

    # unanswerable (~15%): invented items; real items for years the report does not cover — past AND future
    # (v1 only had future years, so FinSumm invented an answer for "Airtel's revenue in FY 2019-20")
    for _ in range(max(5, len(out) // 6)):
        roll = rng.random()
        if roll < 0.35 or not rows:
            item, yr = rng.choice(FAKE_ITEMS), None
            q = rng.choice([f"What was the {item} for {_fy(fy)}?", f"How much did {co} earn from {item} in {_fy(fy)}?"])
        else:
            item = rng.choice(rows)[2].lower()
            yr = fy + 3 if roll < 0.55 else fy - rng.randint(4, 7)
            q = rng.choice([f"What was the {item} for {_fy(yr)}?", f"What was {co}'s {item} in {_fy(yr)}?"])
        chunks = retrieve_statement_pages(f"What was the {item}?", [key], k=2) + _distractors(page_texts, stmt_pages, rng)
        ctx = " ".join(c["text"] for c in chunks)
        if yr and (str(yr) in ctx or f"{yr - 1}-{str(yr)[2:]}" in ctx):
            continue                                  # a multi-year page in the sources does show that year
        rng.shuffle(chunks)
        when = f" for {_fy(yr)}" if yr else ""
        ans = f"The {item}{when} is not found in the report's provided sources."
        out.append(_example(q, chunks or _distractors(page_texts, stmt_pages, rng, 4), key, label, ans, "unanswerable"))
    return out


def _ratio_examples(rows, co, key, label, page_texts, stmt_pages, rng, has_cons) -> list:
    """Current ratio from the balance sheet: both figures shown, then the division (two decimals)."""
    from app.ml.statement_index import retrieve_statement_pages
    by = {}
    for scope, kind, lab, values, years, unit, raw in rows:
        if kind == "balance_sheet":
            by[(scope, lab.lower())] = (values, years, unit, raw)
    out = []
    for scope in ("consolidated", "standalone", "unknown"):
        ca, cl = by.get((scope, "total current assets")), by.get((scope, "total current liabilities"))
        if not (ca and cl) or ca[2] != cl[2]:
            continue
        year = max(set(ca[1]) & set(cl[1]))
        if not cl[0].get(year):
            continue
        sc_name = scope if scope != "unknown" else ("standalone" if has_cons else "")
        sc = f"{sc_name} " if sc_name else ""
        q = f"What was {co}'s {sc}current ratio (current assets divided by current liabilities) as at 31 March {year}?"
        chunks = retrieve_statement_pages(q, [key], k=2)
        if not chunks or "current liabilities" not in " ".join(c["text"].lower() for c in chunks):
            continue
        n = next(i for i, c in enumerate(chunks) if "current liabilities" in c["text"].lower()) + 1
        chunks = chunks + _distractors(page_texts, stmt_pages, rng, 2)
        ratio = ca[0][year] / cl[0][year]
        ans = (f"The {sc}current ratio as at 31 March {year} was **{ratio:.2f}**: total current assets of "
               f"{_printed(ca[3][year], ca[0][year], ca[2])} divided by total current liabilities of "
               f"{_printed(cl[3][year], cl[0][year], cl[2])} [{n}].")
        out.append(_example(q, chunks, key, label, ans, "ratio"))
    return out


def main(smoke: bool = False) -> None:
    _backend()
    rng = random.Random(SEED)
    SFT_DIR.mkdir(parents=True, exist_ok=True)
    if smoke:
        import sqlite3
        fid, path, fy, name = sqlite3.connect("annual_reports.db").execute(
            "select f.id, f.file_path, f.fiscal_year, c.name from filings f join companies c on c.id=f.company_id "
            "where f.file_name like 'adani 25%'").fetchone()
        ex = build_report(Path(path), name, fy, rng, cap=15)
        (SFT_DIR / "smoke.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in ex), encoding="utf-8")
        print(f"smoke: {len(ex)} examples → {SFT_DIR / 'smoke.jsonl'} (format check only, do NOT train on it)")
        return

    with open(TRAIN_DIR / "manifest.csv", newline="", encoding="utf-8") as f:
        reports = list(csv.DictReader(f))
    companies = sorted({r["company"] for r in reports})
    rng.shuffle(companies)
    n_val = max(1, round(0.05 * len(companies)))
    val_companies = set(companies[:n_val])
    train, val = [], []
    for r in reports:
        ex = build_report(TRAIN_DIR / r["file_name"], r["company"], int(r["fiscal_year"]), rng)
        (val if r["company"] in val_companies else train).extend(ex)
        print(f"{r['company']} FY{r['fiscal_year']}: {len(ex)} examples")
    rng.shuffle(train)
    for name, data in (("sft_train.jsonl", train), ("sft_val.jsonl", val)):
        (SFT_DIR / name).write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in data), encoding="utf-8")
    types = {}
    for e in train:
        types[e["type"]] = types.get(e["type"], 0) + 1
    print(f"train {len(train)} · val {len(val)} (val companies: {sorted(val_companies)}) · types {types}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    main(ap.parse_args().smoke)
