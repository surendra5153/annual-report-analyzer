"""
Statement-aware retrieval.

Chunk retrieval answers "what was the consolidated finance cost?" poorly: the
query matches narrative pages (Chairman's letter, MD&A) better than a dense P&L
table, and a 400-character chunk of a statement loses the column headers that
say which year each figure belongs to.

For numeric questions we therefore also retrieve **whole financial-statement
pages**:
  1. every page of the filing is typed once (our PageClassifier + heading rules)
     and tagged with its scope (standalone / consolidated) — cached per filing;
  2. statement pages are ranked with BM25 against the question, preferring the
     scope the question asks for;
  3. the top pages are returned in full (headers, row labels and both year
     columns intact) as extra sources.
"""
import re
from typing import Dict, List, Optional

import fitz
from loguru import logger

from app.ml.bm25 import BM25
from app.ml.label_pages import label_document, scope_of
from app.ml.page_classifier import classify_pages
from app.ml.text_clean import normalize_unicode

_STATEMENT_RULE_LABELS = {"balance_sheet", "profit_loss", "cash_flow", "equity_changes"}
_PAGE_CHARS = 3500          # a full P&L / balance-sheet page fits; keeps the prompt bounded
_INDEX: Dict[str, List[Dict]] = {}

_NUMERIC_Q = re.compile(
    r"revenue|income|profit|loss|asset|liabilit|equity|earnings per share|\beps\b|expense|cost|tax|cash|borrowing|"
    r"debt|inventor|receivable|payable|ebitda|depreciation|amortis|turnover|margin|dividend|capital|reserve|"
    r"how much|percentage|growth|change|increase|decrease", re.IGNORECASE)

_TITLE = {"balance_sheet": "Balance Sheet", "profit_loss": "Statement of Profit and Loss",
          "cash_flow": "Cash Flow Statement", "equity_changes": "Statement of Changes in Equity", "statement": "Financial Statement"}


def is_numeric_question(question: str) -> bool:
    return bool(_NUMERIC_Q.search(question))


def question_scope(question: str) -> Optional[str]:
    q = question.lower()
    if "consolidated" in q:
        return "consolidated"
    if "standalone" in q or "stand-alone" in q:
        return "standalone"
    return None


# A real statement heading is followed by its period ("for the year ended" / "as at"); notes that merely
# mention "…recognised in the Statement of Profit & Loss" are not statements.
_TRUE_HEADING = {
    "profit_loss": re.compile(r"statement\s+of\s+profit\s*(?:and|&)\s*loss[\s|]*(?:account[\s|]*)?for\s+the\s+(?:year|period)", re.I),
    "balance_sheet": re.compile(r"balance\s+sheet[\s|]*as\s+at", re.I),
    "cash_flow": re.compile(r"(?:statement\s+of\s+cash\s+flows?|cash\s+flow\s+statement)[\s|]*for\s+the\s+(?:year|period)", re.I),
    "equity_changes": re.compile(r"statement\s+of\s+changes\s+in\s+equity[\s|]*for\s+the\s+(?:year|period)", re.I),
}
# …or the heading stands alone on its own line (TCS: "Consolidated Balance Sheet" / "(₹ crore)" / "As at …"),
# which a note mentioning "…recognised in the Statement of Profit and Loss" never does. Banks: "Profit and Loss Account".
_CONTD = r"(?:\s*\((?:contd\.?|continued)\))?[ \t]*$"      # Bajaj: "Statement of Profit and Loss (Contd.)"
_LINE_HEADING = {
    "profit_loss": re.compile(r"(?m)^[ \t|]*(?:consolidated |standalone )?(?:statement of profit\s*(?:and|&)\s*loss(?: account)?|"
                              r"profit\s*(?:and|&)\s*loss account)" + _CONTD, re.I),
    "balance_sheet": re.compile(r"(?m)^[ \t|]*(?:consolidated |standalone )?balance sheet" + _CONTD, re.I),
    "cash_flow": re.compile(r"(?m)^[ \t|]*(?:consolidated |standalone )?(?:statement of cash flows?|cash flow statement)" + _CONTD, re.I),
    "equity_changes": re.compile(r"(?m)^[ \t|]*(?:consolidated |standalone )?statement of changes in equity" + _CONTD, re.I),
}
# A wrapped table header ("Outstanding amounts carried in the / Balance Sheet") is not a heading
_DANGLING = re.compile(r"\b(?:the|in|of|and|to|on|per|as|at|from|into|with|by|for)[ \t]*$", re.I)


# Words that may precede a heading on its line; anything else ("…comprise the Standalone Balance Sheet as at…"
# in an auditor's report, "Schedules to the Balance Sheet as at…") means the page is not the statement itself.
_HEADING_PREFIX = re.compile(r"[\s|]*(?:(?:[a-z][\w&.,'()-]*\s+){0,6}(?:limited|ltd\.?)\s+)?(?:(?:consolidated|standalone|audited)\s+)*",
                             re.I)


# Letter-spaced display headings ("S TA N D A L O N E B A L A N C E S H E E T", HDFC Bank FY25)
_SPACED_LINE = re.compile(r"(?:\S{1,3} +){4,}\S{1,3}")
_HEADING_VOCAB = sorted("consolidated standalone statements statement of profit and & loss account balance sheet cash "
                        "flows flow changes in equity for the year ended as at independent auditor's report schedules "
                        "schedule to".split(), key=len, reverse=True)


def _segment(s: str) -> Optional[List[str]]:
    """Split 'standalonebalancesheet' into heading words, or None if it is not made of them."""
    if not s:
        return []
    for w in _HEADING_VOCAB:
        if s.startswith(w):
            rest = _segment(s[len(w):])
            if rest is not None:
                return [w] + rest
    return None


def unspace_headings(text: str) -> str:
    """Rewrite letter-spaced heading lines as normal words; other lines are unchanged."""
    out = []
    for line in text.split("\n"):
        words = _segment(line.replace(" ", "").lower()) if _SPACED_LINE.fullmatch(line.strip()) else None
        out.append(" ".join(words) if words else line)
    return "\n".join(out)


def heading_kind(top: str) -> Optional[str]:
    """Statement type from the page/panel heading (earliest match wins), or None."""
    top = unspace_headings(top)
    hits = []
    for kind in _TRUE_HEADING:
        for rx in (_TRUE_HEADING[kind], _LINE_HEADING[kind]):
            for m in rx.finditer(top):
                line_start = top.rfind("\n", 0, m.start()) + 1
                prefix = top[line_start:m.start()]
                prev_line = next((l for l in reversed(top[:max(line_start - 1, 0)].split("\n")) if l.strip()), "")
                if _HEADING_PREFIX.fullmatch(prefix) and not _DANGLING.search(prev_line):
                    hits.append((m.start(), kind))
                    break
    return min(hits)[1] if hits else None


def _build(filing_id: str, pdf_path: str) -> List[Dict]:
    with fitz.open(pdf_path) as doc:
        raw = [p.get_text() for p in doc]
    norm = [normalize_unicode(t) for t in raw]
    model_labels = classify_pages(raw)
    rule_labels = [l for l, _ in label_document(norm)]
    pages = []
    for i, (text, ml, rl) in enumerate(zip(norm, model_labels, rule_labels)):
        top = unspace_headings(text[:800])
        hk = heading_kind(top)
        if ml == "statement" or rl in _STATEMENT_RULE_LABELS or hk:
            scope = scope_of(top + "\n" + text)
            if scope == "unknown" and pages and pages[-1]["page_number"] == i:
                scope = pages[-1]["scope"]      # continuation page ("…Cash Flow Statement" p.2) carries no scope words
            pages.append({"page_number": i + 1, "kind": hk or "statement", "scope": scope, "text": text})
    logger.info(f"Statement index {filing_id[:8]}: {len(pages)} statement pages of {len(norm)}")
    return pages


def statement_index(filing_id: str, pdf_path: Optional[str] = None) -> List[Dict]:
    """
    Statement pages of a report, cached by key. `pdf_path` lets offline tools (e.g. the
    fine-tuning data builder) index PDFs that are not in the app database.
    """
    if filing_id not in _INDEX and pdf_path:
        try:
            _INDEX[filing_id] = _build(filing_id, pdf_path)
        except Exception as e:
            logger.warning(f"Statement index failed for {pdf_path}: {e}")
            _INDEX[filing_id] = []
    if filing_id not in _INDEX:
        from app.db.database import SessionLocal
        from app.db.models import Filing
        db = SessionLocal()
        try:
            f = db.query(Filing).filter(Filing.id == filing_id).first()
            _INDEX[filing_id] = _build(filing_id, f.file_path) if f and f.file_path else []
        except Exception as e:  # missing PDF etc. — fall back to chunk retrieval only
            logger.warning(f"Statement index failed for {filing_id}: {e}")
            _INDEX[filing_id] = []
        finally:
            db.close()
    return _INDEX[filing_id]


# Which statement holds which line item (domain routing)
_ITEM_TO_KIND = [
    (re.compile(r"cash flow|operating activities|investing activities|financing activities|capex|capital expenditure", re.I), "cash_flow"),
    (re.compile(r"asset|liabilit|equity|inventor|receivable|payable|borrowing|debt|reserve|net worth|share capital|"
                r"cash and cash equivalents|investments as at|as at", re.I), "balance_sheet"),
    (re.compile(r"revenue|income|profit|loss|expense|cost|tax|earnings per share|\beps\b|ebitda|depreciation|"
                r"amortis|turnover|exceptional", re.I), "profit_loss"),
]
_YEARISH = re.compile(r"\b(?:fy\s?)?\d{2,4}(?:\s?-\s?\d{2,4})?\b", re.IGNORECASE)


_STOP = set("what was were is are the of for in at as on by to and did how much which consolidated standalone fy "
             "year years ended march company's company".split())


def _item_terms(question: str) -> List[str]:
    words = re.findall(r"[a-z]+", _YEARISH.sub(" ", question.lower()))
    return [w for w in words if w not in _STOP and len(w) > 2]


def focus_text(text: str, question: str, budget: int) -> str:
    """
    Fit a page into `budget` characters without losing the asked row: keep the
    page header (title, unit, year columns) and a window centred on the line that
    best matches the question's line-item words. Some PDFs put two statements on
    one page (e.g. balance sheet + P&L), so plain truncation can drop the answer.
    """
    if len(text) <= budget:
        return text
    head_len = 450
    terms = _item_terms(question)
    best, best_pos, pos = -1, head_len, 0
    for line in text.splitlines(keepends=True):
        low = line.lower()
        hits = sum(t in low for t in terms)
        if hits > best and pos >= head_len:
            best, best_pos = hits, pos
        pos += len(line)
    window = budget - head_len
    start = max(head_len, best_pos - window // 2)
    return text[:head_len] + "\n[…]\n" + text[start:start + window]


_UNGROUPED = re.compile(r"(?<![\d,.])(-?)(\d{5,})(?![\d,])")


def group_digits(text: str) -> str:
    """
    Indian digit grouping for long ungrouped numbers ("610768" → "6,10,768").
    Some reports (e.g. HAL, ₹ lakh) print 6–8 digit figures without separators,
    and small LLMs drop or repeat digits when copying such strings.
    """
    from app.services.qa_context import _inr
    return _UNGROUPED.sub(lambda m: m.group(1) + _inr(int(m.group(2)), 0), text)


def _page_unit(text: str) -> Optional[str]:
    from app.ml.kpi_clean import detect_report_unit
    unit, counts = detect_report_unit([text])
    return unit if counts else None


def question_kind(question: str) -> Optional[str]:
    for rx, kind in _ITEM_TO_KIND:
        if rx.search(question):
            return kind
    return None


def retrieve_statement_pages(question: str, filing_ids: List[str], k: int = 2, group_numbers: bool = True) -> List[Dict]:
    """Top-k whole statement pages as pseudo-chunks (empty for non-numeric questions)."""
    if not is_numeric_question(question):
        return []
    want_scope = question_scope(question)
    want_kind = question_kind(question)
    candidates = [(fid, p) for fid in filing_ids for p in statement_index(fid)]
    if not candidates:
        return []
    # Years / FY tokens match every page of a report; rank on the line item words only
    query = _YEARISH.sub(" ", question)
    scores = BM25([p["text"] for _, p in candidates]).get_scores(query)
    ranked = []
    for (fid, p), s in zip(candidates, scores):
        s += 0.5                                  # every statement page stays a candidate
        if p["kind"] != "statement":
            s *= 1.5                              # typed from a real statement heading (precise)
        if want_kind and p["kind"] == want_kind:
            s *= 3.0                              # right statement for this line item
        if want_scope:
            if p["scope"] == want_scope:
                s *= 1.5
            elif p["scope"] != "unknown":
                s *= 0.3                          # wrong scope: last resort only
        elif p["scope"] == "consolidated":
            s *= 1.3                              # headline figures are conventionally consolidated
        ranked.append((s, fid, p))
    ranked.sort(key=lambda x: x[0], reverse=True)

    out, used = [], set()
    for s, fid, p in ranked:
        if len(out) >= k:
            break
        if (fid, p["page_number"]) in used:
            continue
        # Statements run over consecutive pages (P&L → EPS on the next page; assets → liabilities):
        # attach the continuation page of the same statement and scope to the same source.
        by_page = {q["page_number"]: q for q in statement_index(fid)}
        nxt = by_page.get(p["page_number"] + 1)
        group = [p] + ([nxt] if nxt and nxt["kind"] in (p["kind"], "statement") and nxt["scope"] in (p["scope"], "unknown") else [])
        used.update((fid, q["page_number"]) for q in group)
        per_page = _PAGE_CHARS if len(group) == 1 else _PAGE_CHARS * 2 // 3
        scope = f"{p['scope'].capitalize()} " if p["scope"] != "unknown" else ""
        pages_label = "–".join(str(q["page_number"]) for q in group)
        unit = _page_unit(p["text"])
        unit_note = f" · amounts in ₹ {unit} as printed" if unit else ""
        body = "\n".join(f"(page {q['page_number']})\n{focus_text(q['text'], question, per_page)}" for q in group)
        if group_numbers:
            body = group_digits(body)     # "376766" → "3,76,766": small LLMs drop or repeat digits in long runs
        out.append({
            "id": f"stmt-{fid}-{p['page_number']}",
            "text": f"[{scope}{_TITLE[p['kind']]} — full page{'s ' + pages_label if len(group) > 1 else ''}{unit_note}]\n{body}",
            "metadata": {"filing_id": fid, "page_number": p["page_number"], "chunk_type": "statement_page"},
            "hybrid_score": 0.8,
        })
    return out
