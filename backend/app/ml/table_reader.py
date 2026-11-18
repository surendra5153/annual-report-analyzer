"""
Deterministic table reader for financial statements (no AI).

Reads the exact cell a question asks for, e.g. "consolidated total income for FY 2024-25", straight from
the statement page, and computes year-on-year changes in Python.

Why: the LLM's remaining errors are mechanical. It reads the wrong year column or the wrong row, converts
₹ lakh into rupees, and gets percentages wrong (notebook 06). A geometric reading of the table removes
all four.

How
  1. Table reconstruction from word positions (PyMuPDF `get_text("words")`):
     * wide pages (two printed pages side by side) are split into panels;
     * period headers ("March 31, 2025", "31st March 2026", "2025-26") give the year columns;
     * every number is assigned to the nearest year column (note-number columns are too far away and are
       dropped);
     * words left of the value columns form the row label; wrapped labels are joined.
  2. Row matching: a dictionary of canonical line items with synonyms, plus exact-phrase fallback.
  3. Confidence: one matching row (or duplicates agreeing), scope consistent with the question, value
     present for the asked year, unit known. Confident results are answered without the LLM.
"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import fitz

from app.ml.kpi_clean import detect_report_unit
from app.ml.statement_index import heading_kind, question_kind, question_scope, statement_index
from app.ml.text_clean import normalize_unicode

# ── Table reconstruction ─────────────────────────────────────────────────────

_NUM_TOKEN = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?$")
_YEAR_TOKEN = re.compile(r"^(?:FY)?(19|20)(\d{2})(?:-(\d{2}))?[,.]?$")
_ROMAN = re.compile(r"^(?:[ivxl]+|[a-z]|\d{1,2})[.)]?$", re.IGNORECASE)


@dataclass
class Row:
    label: str
    values: Dict[int, float]
    y: float
    nil: bool = False          # values printed as "-" / "-*" (nil): a data row, not a section header
    raw: Dict[int, str] = field(default_factory=dict)   # each value exactly as printed ("(1,116.49)")


@dataclass
class Table:
    page: int
    panel: int
    scope: str
    kind: str
    unit: Optional[str]
    years: List[int]
    rows: List[Row] = field(default_factory=list)
    title: str = ""


def parse_number(tok: str) -> Optional[float]:
    t = tok.strip().replace("₹", "")
    if not _NUM_TOKEN.match(t):
        return None
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    try:
        v = float(t.strip("()").lstrip("-").replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


_DATE_TOKEN = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-]((?:19|20)\d{2})[,.]?$")   # "31.03.2026", "31/03/2026"


def _fiscal_year(tok: str) -> Optional[int]:
    d = _DATE_TOKEN.match(tok.strip())
    if d:
        month, year = int(d.group(2)), int(d.group(3))
        return (year if month <= 3 else year + 1) if 1 <= month <= 12 and 1990 <= year <= 2040 else None
    m = _YEAR_TOKEN.match(tok.strip())
    if not m:
        return None
    year = int(m.group(1) + m.group(2))
    if m.group(3):                      # "2025-26" → FY2026
        year = int(m.group(1) + m.group(3)) if int(m.group(3)) > int(m.group(2)) else year + 1
    return year if 1990 <= year <= 2040 else None


def _panels(words, width: float) -> List[list]:
    """Split a two-page spread into left / right panels."""
    if width < 800:
        return [words]
    mid = width / 2
    return [[w for w in words if w[0] < mid], [w for w in words if w[0] >= mid]]


def _lines(words, tol: float = 4.0) -> List[list]:
    """Group words into visual lines by vertical centre."""
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines, current, cy = [], [], None
    for w in words:
        y = (w[1] + w[3]) / 2
        if cy is None or abs(y - cy) <= tol:
            current.append(w)
            cy = y if cy is None else (cy + y) / 2
        else:
            lines.append(sorted(current, key=lambda v: v[0]))
            current, cy = [w], y
    if current:
        lines.append(sorted(current, key=lambda v: v[0]))
    return lines


def _year_columns(lines) -> List[Tuple[float, int]]:
    """(x-centre, fiscal year) of the period columns, from the header lines above the first value row."""
    cols: List[Tuple[float, int]] = []
    for line in lines[:40]:
        found = [((w[0] + w[2]) / 2, _fiscal_year(w[4])) for w in line]
        found = [(x, y) for x, y in found if y]
        if len(found) >= 2 and len({y for _, y in found}) >= 2:
            # keep the right-most header line pair (value columns sit right of the labels)
            cols = sorted(found)
            break
    # one year per column, left to right
    out, seen = [], set()
    for x, y in cols:
        if y not in seen:
            out.append((x, y))
            seen.add(y)
    return out


_SECTION_HEAD = re.compile(r"^\(?(?:\d{1,2}|[IVX]{1,4})[.)]\s+\S")      # "(1) Non-current assets", "II. Expenses"
_ENUM_PREFIX = re.compile(r"^\(?(?:\d{1,2}|[ivxl]{1,4}|[a-z])[.)]\s*", re.I)
_NIL_TOKEN = re.compile(r"^[-–—]\*?$")
_THOUSANDS_TAIL = re.compile(r"^\d{3}(?:,\d{3})*(?:\.\d+)?\)?$")


def _merge_split_numbers(line) -> list:
    """Some fonts break '9,453' into the words '9' and '453' with no visible comma: rejoin them."""
    out = []
    for w in line:
        prev = out[-1] if out else None
        if (prev and re.fullmatch(r"\(?-?\d{1,3}", prev[4]) and _THOUSANDS_TAIL.match(w[4])
                and 0 <= w[0] - prev[2] < 2.0):
            out[-1] = (prev[0], min(prev[1], w[1]), w[2], max(prev[3], w[3]), f"{prev[4]},{w[4]}")
        else:
            out.append(w)
    return out


def _clean_label(words) -> str:
    toks = [w[4] for w in words]
    while toks and (_ROMAN.match(toks[0]) or toks[0] in {"-", "–", "•"}):
        toks = toks[1:]
    label = " ".join(toks)
    label = re.sub(r"\((?:[ivxl+\-]+|[IVXL+\-]+)\)$", "", label).strip()   # "(I+II)", "(IV)"
    return label


def read_tables(pdf_path: str, page_number: int, scope: str = "unknown", kind: str = "statement") -> List[Table]:
    return list(_read_tables_cached(pdf_path, page_number, scope, kind))


@lru_cache(maxsize=512)
def _read_tables_cached(pdf_path: str, page_number: int, scope: str, kind: str) -> Tuple[Table, ...]:
    with fitz.open(pdf_path) as doc:
        page = doc[page_number - 1]
        words = [(w[0], w[1], w[2], w[3], normalize_unicode(w[4])) for w in page.get_text("words")]
        width = page.rect.width
        text = normalize_unicode(page.get_text())
    unit_page, counts = detect_report_unit([text])
    tables = []
    for pi, panel in enumerate(_panels(words, width)):
        lines = _lines(panel)
        cols = _year_columns(lines)
        if len(cols) < 2:
            continue
        spacing = min(b[0] - a[0] for a, b in zip(cols, cols[1:])) or 60
        first_col_x = cols[0][0]
        panel_text = " ".join(w[4] for w in panel)
        p_unit, p_counts = detect_report_unit([panel_text])
        unit = p_unit if p_counts else (unit_page if counts else None)
        p_scope = ("consolidated" if "consolidated" in panel_text[:400].lower()
                   else "standalone" if "standalone" in panel_text[:400].lower() else scope)
        # Statement type per panel: a spread can hold a balance sheet and a P&L side by side
        p_kind = heading_kind("\n".join(" ".join(w[4] for w in ln) for ln in lines)[:800]) or kind

        rows: List[Row] = []
        pending_prefix = ""
        for line in lines:
            line = _merge_split_numbers(line)
            values: Dict[int, float] = {}
            raws: Dict[int, str] = {}
            label_words = []
            nil = False
            for w in line:
                xc = (w[0] + w[2]) / 2
                in_values = w[0] > first_col_x - spacing * 0.75
                nil = nil or (in_values and bool(_NIL_TOKEN.match(w[4])))
                v = parse_number(w[4]) if in_values else None
                if v is not None:
                    x, year = min(cols, key=lambda c: abs(c[0] - xc))
                    if abs(x - xc) <= spacing * 0.6 and year not in values:
                        values[year] = v
                        raws[year] = w[4]
                    continue
                if w[2] < first_col_x - spacing * 0.5 and not (w[4] in {"-", "–"} and w[0] > first_col_x - spacing):
                    label_words.append(w)
            # drop trailing note-number tokens from the label ("Finance Costs 37", "Goods, 39")
            label = re.sub(r"\s+\d{1,2}[A-Z]?(?:\s*(?:&|,)\s*\d{1,2}[A-Z]?)*$", "", _clean_label(label_words))
            if values and all(1990 <= v <= 2040 or v == 31 for v in values.values()):
                continue                                               # date header ("31st March 2026")
            if values:
                headers = [r for r in reversed(rows) if not r.values and not r.nil]
                # a section total belongs to the numbered section ("(1) Non-current assets"), not to the
                # nearest sub-heading ("(i) Financial assets") printed just above its last rows
                header = next((r for r in headers if _SECTION_HEAD.match(r.label)), headers[0] if headers else None)
                if pending_prefix:
                    full = (pending_prefix + " " + label).strip()
                elif label[:1].islower() or label.lower().startswith(("and ", "& ", "of ")):
                    # value line continuing a long label printed on the line above
                    if rows and not rows[-1].values and not rows[-1].nil:
                        full = (rows.pop().label + " " + label).strip()
                    else:
                        full = label
                elif not label and rows and not rows[-1].values and not rows[-1].nil and len(rows[-1].label.split()) > 3:
                    full = rows.pop().label                            # long label printed fully on the line above
                elif not label and header is not None:
                    full = f"Total {_ENUM_PREFIX.sub('', header.label).lower()}"   # unlabelled total under a section header
                else:
                    full = label
                rows.append(Row(label=full, values=values, y=line[0][1], raw=raws))
                pending_prefix = ""
            elif label and nil:
                pending_prefix = ""
                rows.append(Row(label=label, values={}, y=line[0][1], nil=True))   # "Cash on hand  -*  -*"
            elif label:
                low = label[:1]
                if rows and (low.islower() or label.lower().startswith(("and ", "& ", "of "))):
                    rows[-1].label += " " + label                     # wrapped continuation of the row above
                elif label.endswith((",", "-", " of", " and", " &", " /")):
                    pending_prefix = label                             # label continues on the value line
                else:
                    pending_prefix = ""
                    rows.append(Row(label=label, values={}, y=line[0][1]))   # section header / context row
        tables.append(Table(page=page_number, panel=pi, scope=p_scope, kind=p_kind, unit=unit,
                            years=[y for _, y in cols], rows=rows, title=panel_text[:120]))
    return tuple(tables)


# ── Row matching ─────────────────────────────────────────────────────────────

ITEMS: Dict[str, List[str]] = {
    "total income": ["total income", "total revenue", "income total"],
    "revenue from operations": ["revenue from operations", "revenue from operation", "revenue from contracts with customers"],
    "other income": ["other income"],
    "total expenses": ["total expenses"],
    "finance costs": ["finance costs", "finance cost", "interest and finance charges"],
    "employee benefits expense": ["employee benefits expense", "employee benefit expense", "employee benefits expenses"],
    "depreciation": ["depreciation and amortisation expense", "depreciation and amortization expense",
                     "depreciation amortisation impairment expense", "depreciation amortisation and impairment expense",
                     "depreciation and amortisation expenses"],
    "profit before tax": ["profit before tax", "profit loss before tax", "profit before tax from continuing operations"],
    "profit for the year": ["profit for the year", "profit for the period", "profit loss for the period",
                            "profit loss for the year", "profit after tax", "net profit for the year"],
    "total tax expense": ["total tax expense", "total tax expenses", "tax expense"],
    "exceptional items": ["exceptional items", "exceptional items net"],
    "basic eps": ["earnings per share basic", "basic"],
    "diluted eps": ["earnings per share diluted", "diluted"],
    "total assets": ["total assets"],
    "total equity": ["total equity"],
    "total liabilities": ["total liabilities"],
    "total current assets": ["total current assets", "current assets"],
    "total current liabilities": ["total current liabilities", "current liabilities"],
    "total non-current assets": ["total non current assets", "non current assets"],
    "inventories": ["inventories"],
    "trade receivables": ["trade receivables"],
    "cash and cash equivalents": ["cash and cash equivalents", "cash cash equivalents"],
    "equity share capital": ["equity share capital", "share capital"],
    "other equity": ["other equity"],
    "net cash from operating activities": ["net cash from operating activities", "net cash generated from operating activities",
                                           "net cash flow from operating activities", "net cash inflow from operating activities",
                                           "net cash generated from used in operating activities"],
}
# question phrase → item (longest phrase wins)
_Q_PHRASES = sorted([(p, item) for item, ps in {
    **{k: [k] for k in ITEMS},
    "total income": ["total income", "total revenue"],
    "profit for the year": ["profit for the year", "profit after tax", "net profit", "pat", "profit for fy", "profit or loss after tax",
                            "consolidated profit", "standalone profit", "profit for the period"],
    "profit before tax": ["profit before tax", "pbt", "profit before tax from continuing operations"],
    "basic eps": ["basic earnings per share", "basic eps", "earnings per share", "eps"],
    "diluted eps": ["diluted earnings per share", "diluted eps"],
    "finance costs": ["finance costs", "finance cost", "interest cost"],
    "employee benefits expense": ["employee benefits expense", "employee cost", "employee expenses"],
    "total tax expense": ["total tax expense", "tax expense"],
    "total assets": ["total assets"],
    "inventories": ["inventories", "inventory"],
}.items() for p in ps], key=lambda x: -len(x[0]))

_CHANGE_Q = re.compile(r"\bchange|grow|growth|increase|decrease|decline|percent|%|compared", re.IGNORECASE)


def _norm(s: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _match_phrase(question: str) -> Tuple[Optional[str], Optional[str]]:
    q = " " + _norm(question) + " "
    for phrase, item in _Q_PHRASES:
        if f" {phrase} " in q:
            # "profit before tax" must not be read as "profit for the year"
            if item == "profit for the year" and "before tax" in q:
                continue
            if item == "basic eps" and "diluted" in q:
                continue
            return item, phrase
    return None, None


def question_item(question: str) -> Optional[str]:
    return _match_phrase(question)[0]


# Words a plain "what was <item> for <period>" question may contain besides the item itself
_ALLOWED = set("""what was were is are the of for in at as on by to did how much which a an its it
fy year years ended ending end march st financial period consolidated standalone stand alone
percentage percent change changed grow grew growth increase increased decrease decreased decline declined
compared with from previous prior and over company companys group reported report reports value amount figure
total""".split())


def extra_qualifiers(question: str, phrase: Optional[str]) -> List[str]:
    """
    Content words outside item / scope / period / change vocabulary, e.g.
    "attributable to owners", "in Antarctica", "per employee". If any remain,
    the question is more specific than a statement cell, so the reader must not answer.
    """
    words = _norm(question).split()
    item_words = set((phrase or "").split())
    return [w for w in words if w not in _ALLOWED and w not in item_words and len(w) > 1]


def _generic_phrase(question: str) -> Optional[str]:
    """Fallback item for line items missing from ITEMS: the question's content words, e.g. 'network operating expenses'."""
    words = [w for w in _norm(question).split() if w not in _ALLOWED]
    return " ".join(words) if 1 <= len(words) <= 6 else None


def question_year(question: str, default: int) -> int:
    q = question.replace("–", "-")
    m = re.search(r"FY\s?(\d{4})\s?-\s?(\d{2,4})", q, re.I)
    if m:
        end = m.group(2)
        return int(end) if len(end) == 4 else int(m.group(1)[:2] + end)
    m = re.search(r"FY\s?(\d{4})\b", q, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"March,?\s*(?:31(?:st)?,?\s*)?(\d{4})|31(?:st)?\s+March,?\s*(\d{4})", q, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    return default


def _row_score(label: str, item: str) -> float:
    lab = _norm(label)
    if item not in ITEMS:                       # generic phrase from the question: exact label only
        return 1.0 if lab == item else 0.0
    best = 0.0
    for syn in ITEMS[item]:
        if lab == syn:
            return 1.0
        if lab.startswith(syn + " ") and len(lab) - len(syn) <= 25:
            best = max(best, 0.9)
        best = max(best, SequenceMatcher(None, lab, syn).ratio() * 0.95)
    return best


# ── Answering ────────────────────────────────────────────────────────────────

@dataclass
class ReaderResult:
    confident: bool
    item: Optional[str] = None
    label: str = ""
    value: Optional[float] = None
    prior: Optional[float] = None
    year: Optional[int] = None
    prior_year: Optional[int] = None
    change_pct: Optional[float] = None
    unit: Optional[str] = None
    scope: str = "unknown"
    page: Optional[int] = None
    kind: str = ""
    reason: str = ""
    wants_change: bool = False


def _eps_label(rows: List[Row], idx: int, item: str) -> Optional[str]:
    """
    Resolve an EPS row inside its block. Reports print EPS as
      Earnings per share — Basic / Diluted                         (simple)
      … — Continuing Ops / Discontinued Ops / Continuing and Discontinued (split, one figure for basic & diluted)
      Continuing Ops: Basic, Diluted · Discontinued: … · Continuing and Discontinued: Basic, Diluted
    The headline EPS is the total (continuing + discontinued) or the plain Basic row;
    discontinued-only rows are never EPS. Returns a label for _row_score, or None to skip.
    """
    window = rows[max(0, idx - 9):idx]
    header = next((r for r in reversed(window) if "earnings per" in r.label.lower()), None)
    own = _norm(rows[idx].label)
    if header is None:
        return rows[idx].label if "earnings per" in rows[idx].label.lower() else None
    context = next((_norm(r.label) for r in reversed(rows[max(0, idx - 3):idx]) if not r.values), "")
    if "discontinued" in own and "continuing and discontinued" not in own:
        return None
    if "discontinued" in context and "continuing and discontinued" not in context and "continuing and discontinued" not in own:
        return None
    both = "basic" in _norm(header.label) and "diluted" in _norm(header.label)
    kind = "diluted" if item == "diluted eps" else "basic"
    if own in ("basic", "diluted"):
        return f"earnings per share {own}" if own == kind else None
    if own in ("basic and diluted", "basic diluted", "basic diluted eps"):
        return f"earnings per share {kind}"
    if both and "continuing and discontinued" in own:
        return f"earnings per share {kind}"            # total EPS: one figure for basic and diluted
    return None


def read(question: str, filing_id: str, pdf_path: str, fiscal_year: int) -> ReaderResult:
    item, phrase = _match_phrase(question)
    if item:
        extra = extra_qualifiers(question, phrase)
        if extra:
            return ReaderResult(False, item=item, reason=f"question has extra qualifiers {extra}")
    else:
        item = _generic_phrase(question)     # exact row-label match only (see _row_score)
        if not item:
            return ReaderResult(False, reason="question item not recognised")
    return read_item(item, filing_id, pdf_path, question_year(question, fiscal_year),
                     want_scope=question_scope(question), want_kind=question_kind(question),
                     wants_change=bool(_CHANGE_Q.search(question)))


def read_item(item: str, filing_id: str, pdf_path: str, year: int, want_scope: Optional[str] = None,
              want_kind: Optional[str] = None, wants_change: bool = False) -> ReaderResult:
    """Read one canonical line item (see ITEMS) for `year` from the filing's statement pages."""
    pages = statement_index(filing_id, pdf_path)
    has_consolidated = any(p["scope"] == "consolidated" for p in pages)

    candidates = []   # (rank, row_score, table, row)
    for p in pages:
        # unlabelled statements are standalone by Indian convention when the report also has consolidated ones
        p_scope = p["scope"] if p["scope"] != "unknown" else ("standalone" if has_consolidated else "unknown")
        for t in read_tables(pdf_path, p["page_number"], p_scope, p["kind"]):
            t_scope = t.scope if t.scope != "unknown" else p_scope
            if want_scope and t_scope not in (want_scope, "unknown"):
                continue
            if year not in t.years:
                continue
            rank = 0.0
            rank += 2.0 if t.kind in ("profit_loss", "balance_sheet", "cash_flow") else 0.0
            rank += 1.5 if want_kind and t.kind == want_kind else 0.0
            rank += 1.0 if (want_scope and t_scope == want_scope) or (not want_scope and t_scope == "consolidated") else 0.0
            for i, r in enumerate(t.rows):
                if year not in r.values:
                    continue
                label = r.label
                if item in ("basic eps", "diluted eps"):
                    label = _eps_label(t.rows, i, item)
                    if label is None:
                        continue
                s = _row_score(label, item)
                if s >= 0.85:
                    candidates.append((rank, s, t, r, t_scope))
    if not candidates:
        return ReaderResult(False, item=item, year=year, reason="no matching row on statement pages", wants_change=wants_change)

    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    best_rank, best_score, t, r, t_scope = candidates[0]
    rivals = [c for c in candidates[1:] if c[0] == best_rank and c[1] >= best_score - 1e-9]
    if any(abs(c[3].values.get(year, 0) - r.values[year]) > 1e-6 for c in rivals):
        return ReaderResult(False, item=item, year=year, reason="several rows match with different values",
                            wants_change=wants_change)
    if not t.unit and item not in ("basic eps", "diluted eps"):
        return ReaderResult(False, item=item, year=year, reason="unit unknown", wants_change=wants_change)

    prior_year = max((y for y in t.years if y < year), default=None)
    prior = r.values.get(prior_year) if prior_year else None
    change = (r.values[year] - prior) / abs(prior) * 100 if prior not in (None, 0) else None
    if wants_change and change is None:
        return ReaderResult(False, item=item, year=year, reason="prior-year value missing", wants_change=True)
    return ReaderResult(True, item=item, label=r.label, value=r.values[year], prior=prior, year=year,
                        prior_year=prior_year, change_pct=change, unit=t.unit, scope=t_scope, page=t.page,
                        kind=t.kind, wants_change=wants_change)


# ── Rendering ────────────────────────────────────────────────────────────────

_TO_CRORE = {"lakh": 0.01, "million": 0.1, "billion": 100.0, "thousand": 1e-4}
_KIND_TITLE = {"profit_loss": "Statement of Profit and Loss", "balance_sheet": "Balance Sheet",
               "cash_flow": "Cash Flow Statement", "equity_changes": "Statement of Changes in Equity",
               "statement": "financial statements"}


def _fy(y: int) -> str:
    return f"FY {y - 1}-{str(y)[2:]}"


def _money(v: float, unit: Optional[str], per_share: bool) -> str:
    from app.services.qa_context import _inr
    sign = "-" if v < 0 else ""
    if per_share:
        return f"{sign}₹{abs(v):,.2f} per share"
    digits = 2 if abs(v) % 1 else 0
    # Indian grouping for lakh/crore, western grouping for million/billion (as the report prints them)
    grouped = f"{abs(v):,.{digits}f}" if unit in ("million", "billion", "thousand") else _inr(abs(v), digits)
    text = f"{sign}₹{grouped} {unit}"
    if unit in _TO_CRORE:
        crore = abs(v) * _TO_CRORE[unit]
        text += f" (≈ {sign}₹{_inr(crore, 2 if crore < 100 else 0)} crore)"
    return text


def render_answer(res: ReaderResult) -> str:
    per_share = res.item in ("basic eps", "diluted eps")
    scope = f"{res.scope.capitalize()} " if res.scope in ("consolidated", "standalone") else ""
    period = f"as at 31 March {res.year}" if res.kind == "balance_sheet" else f"for {_fy(res.year)}"
    text = f"**{scope}{res.label.strip()}** {period} was **{_money(res.value, res.unit, per_share)}**"
    if res.prior is not None and res.change_pct is not None:
        direction = "up" if res.change_pct >= 0 else "down"
        prior_period = f"31 March {res.prior_year}" if res.kind == "balance_sheet" else _fy(res.prior_year)
        text += (f", {direction} **{abs(res.change_pct):.2f}%** from {_money(res.prior, res.unit, per_share)} "
                 f"in {prior_period}")
    text += f" [1].\n\n*Read directly from the {scope.lower()}{_KIND_TITLE.get(res.kind, 'financial statements')}, page {res.page}.*"
    return text


def source_excerpt(res: ReaderResult) -> str:
    """Text used for the citation chip and for highlighting the row in the PDF."""
    vals = " ".join(str(v) for v in (res.value, res.prior) if v is not None)
    return f"{res.label} {vals}"
