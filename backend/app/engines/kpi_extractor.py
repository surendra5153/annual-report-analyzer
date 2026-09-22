"""
KPI Extraction Engine — v3
Two-pass extraction:
  1. Deterministic table scan with Indian INDAS naming aliases,
     multi-column label detection, and robust number parsing
  2. LLM extraction for narrative-embedded figures not in tables
  3. Sanity-check verification pass

Key fixes vs v2:
  - Check columns 0, 1, AND 2 for KPI label (not just col 0 — fixes empty-first-cell tables)
  - Full set of Indian INDAS / Companies Act naming aliases per KPI
  - _parse_indian_number handles negative parenthetical format (1,234) → -1234
  - LLM pass prioritises financial highlights and P&L pages
  - Deduplication: if same canonical KPI found multiple times, keep the one from the
    earliest page (most likely the primary statement, not a note)
"""
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from loguru import logger

from app.core.config import settings
from app.core.llm_client import chat_complete_json


# ── KPI definitions ────────────────────────────────────────────────────────
# Each entry: (canonical_name, category, [alias regexes])
# Aliases cover both abbreviated names and full INDAS / Companies Act phrasing.

KPI_DEFS: List[Tuple[str, str, List[str]]] = [
    ("Total Revenue", "Revenue", [
        r"total\s+revenue",
        r"total\s+income",
        r"revenue\s+from\s+operations",
        r"net\s+revenue",
        r"gross\s+revenue",
        r"net\s+sales",
        r"consolidated\s+revenue",
    ]),
    ("Revenue from Operations", "Revenue", [
        r"revenue\s+from\s+operations",
        r"net\s+revenue\s+from\s+operations",
        r"sales\s+and\s+services",
        r"turnover",
        r"income\s+from\s+operations",
    ]),
    ("Other Income", "Revenue", [
        r"other\s+income",
        r"non.?operating\s+income",
        r"miscellaneous\s+income",
    ]),
    ("Gross Profit", "Profitability", [
        r"gross\s+profit",
        r"gross\s+margin",
    ]),
    ("EBITDA", "Profitability", [
        r"\bebitda\b",
        r"earnings\s+before\s+interest.*?depreciation",
        r"operating\s+profit\s+before\s+depreciation",
        r"profit\s+before\s+depreciation.*?interest.*?tax",
        r"\bebidta\b",  # common typo in Indian reports
    ]),
    ("Operating Profit (EBIT)", "Profitability", [
        r"\bebit\b(?!\s*da)",
        r"operating\s+profit",
        r"profit\s+from\s+operations",
        r"profit\s+before\s+interest\s+and\s+tax",
        r"profit\s+before\s+finance\s+costs\s+and\s+tax",
    ]),
    ("Finance Costs", "Profitability", [
        r"finance\s+costs?",
        r"interest\s+expense",
        r"borrowing\s+costs?",
        r"financial\s+charges",
    ]),
    ("Depreciation & Amortization", "Profitability", [
        r"depreciation\s+and\s+amortis",
        r"depreciation\s+and\s+amortiz",
        r"depreciation[\s,]+amortis",
        r"\bd\s*&\s*a\b",
        r"depletion.*?depreciation",
    ]),
    ("Profit Before Tax (PBT)", "Profitability", [
        r"\bpbt\b",
        r"profit\s+before\s+tax",
        r"profit\s+before\s+taxation",
        r"profit\s+before\s+income\s+tax",
        r"earnings\s+before\s+tax",
    ]),
    ("Profit After Tax (PAT) / Net Profit", "Profitability", [
        r"\bpat\b",
        r"profit\s+after\s+tax",
        r"net\s+profit",
        r"profit\s+for\s+the\s+(year|period|quarter)",
        r"net\s+income",
        r"profit\s+attributable\s+to\s+(owners|shareholders|equity\s+holders)",
        r"total\s+comprehensive\s+income",
    ]),
    ("Total Assets", "Balance Sheet", [
        r"total\s+assets",
    ]),
    ("Total Liabilities", "Balance Sheet", [
        r"total\s+liabilit",
        r"total\s+liabilities\s+and\s+equity",
    ]),
    ("Total Equity / Shareholders Equity", "Balance Sheet", [
        r"total\s+equity",
        r"shareholders.?\s*equity",
        r"stockholders.?\s*equity",
        r"net\s+worth",
        r"total\s+net\s+worth",
        r"equity\s+attributable\s+to\s+(owners|shareholders)",
        r"total\s+funds",
    ]),
    ("Current Assets", "Balance Sheet", [
        r"^current\s+assets$",
        r"total\s+current\s+assets",
    ]),
    ("Current Liabilities", "Balance Sheet", [
        r"^current\s+liabilit",
        r"total\s+current\s+liabilit",
    ]),
    ("Cash and Cash Equivalents", "Balance Sheet", [
        r"cash\s+and\s+cash\s+equivalent",
        r"cash\s+and\s+bank\s+balance",
        r"cash\s+and\s+bank",
        r"^cash\s+balance",
    ]),
    ("Debt (Total Borrowings)", "Balance Sheet", [
        r"total\s+borrowing",
        r"total\s+debt",
        r"long.?term\s+borrowing",
        r"short.?term\s+borrowing",
        r"total\s+indebtedness",
        r"interest.?bearing\s+(liabilit|debt|borrowing)",
        r"total\s+financial\s+liabilit",
    ]),
    ("Capital Expenditure (CapEx)", "Cash Flow", [
        r"\bcapex\b",
        r"capital\s+expenditure",
        r"purchase\s+of\s+(property|fixed\s+assets|ppe|tangible)",
        r"addition\s+to\s+(fixed\s+assets|ppe|property|tangible)",
        r"acquisition\s+of\s+(property|fixed\s+assets|ppe)",
    ]),
    ("Operating Cash Flow", "Cash Flow", [
        r"cash\s+(flow|generated)\s+from\s+operat",
        r"net\s+cash\s+(from|generated\s+by)\s+operat",
        r"operating\s+cash\s+flow",
        r"cash\s+flow\s+from\s+operations",
    ]),
    ("Free Cash Flow", "Cash Flow", [
        r"free\s+cash\s+flow",
        r"\bfcf\b",
    ]),
    ("Earnings Per Share (EPS)", "Per Share", [
        r"\beps\b",
        r"earnings\s+per\s+share",
        r"basic\s+eps",
        r"diluted\s+eps",
        r"basic\s+earnings\s+per\s+(share|equity\s+share)",
        r"diluted\s+earnings\s+per\s+(share|equity\s+share)",
        r"earnings\s+per\s+equity\s+share",
    ]),
    ("Book Value Per Share", "Per Share", [
        r"book\s+value\s+per\s+(equity\s+)?share",
        r"nav\s+per\s+share",
        r"net\s+asset\s+value\s+per\s+share",
    ]),
    ("Dividend Per Share", "Per Share", [
        r"dividend\s+per\s+(equity\s+)?share",
        r"\bdps\b",
        r"dividend\s+declared\s+per\s+share",
        r"dividend\s+paid\s+per\s+share",
    ]),
    ("Return on Equity (ROE) %", "Ratios", [
        r"\broe\b",
        r"return\s+on\s+equity",
        r"return\s+on\s+net\s+worth",
        r"return\s+on\s+shareholders",
    ]),
    ("Return on Assets (ROA) %", "Ratios", [
        r"\broa\b",
        r"return\s+on\s+assets",
        r"return\s+on\s+total\s+assets",
    ]),
    ("Return on Capital Employed (ROCE) %", "Ratios", [
        r"\broce\b",
        r"return\s+on\s+capital\s+employed",
    ]),
    ("Debt-to-Equity Ratio", "Ratios", [
        r"debt.to.equity",
        r"d/e\s+ratio",
        r"gearing\s+ratio",
        r"leverage\s+ratio",
        r"net\s+debt\s+to\s+equity",
    ]),
    ("Current Ratio", "Ratios", [
        r"current\s+ratio",
        r"liquidity\s+ratio",
    ]),
    ("Net Profit Margin %", "Ratios", [
        r"net\s+profit\s+margin",
        r"net\s+margin",
        r"profit\s+margin",
        r"pat\s+margin",
    ]),
    ("Interest Coverage Ratio", "Ratios", [
        r"interest\s+coverage",
        r"debt\s+service\s+coverage",
        r"\bicr\b",
    ]),
    ("Inventory Turnover", "Ratios", [
        r"inventory\s+turnover",
        r"stock\s+turnover",
    ]),
]

# Pre-compile all patterns
_COMPILED: List[Tuple[str, str, List[re.Pattern]]] = [
    (name, cat, [re.compile(alias, re.IGNORECASE) for alias in aliases])
    for name, cat, aliases in KPI_DEFS
]

KPI_NAMES = [name for name, _, _ in KPI_DEFS]
KPI_CATEGORY = {name: cat for name, cat, _ in KPI_DEFS}


# ── Dataclass ──────────────────────────────────────────────────────────────

@dataclass
class ExtractedKPI:
    name: str
    value: Optional[float]
    unit: str
    currency: str
    page_number: Optional[int]
    source_text: str
    is_verified: bool
    verification_note: str
    category: str


# ── Number parsing ─────────────────────────────────────────────────────────

def _parse_number(raw: str) -> Optional[float]:
    """
    Parse financial numbers from Indian annual reports:
    - Standard:           1,23,456.78  →  123456.78
    - Negative parenth:   (1,23,456)   → -123456.0
    - Currency prefix:    ₹1,234       →  1234.0
    - Footnote markers:   45,678*      →  45678.0
    - Plain negative:     -1,234.56    → -1234.56
    Returns None for non-numeric cells (dashes, blanks, text).
    """
    text = raw.strip()
    if not text or text in ('-', '—', '–', 'N/A', 'NA', 'Nil', 'nil', '-', ''):
        return None

    # Strip currency symbols, footnote markers, spaces
    text = re.sub(r'[₹$€£#@\*†‡\s]', '', text)
    if not text:
        return None

    negative = False

    # Parenthetical negative: (1,234) or (1,234.56)
    m = re.fullmatch(r'\(([0-9,]+(?:\.[0-9]+)?)\)', text)
    if m:
        text = m.group(1)
        negative = True

    # Strip trailing suffixes: Cr, Crore, Mn, Million, Bn, Billion, Lakh
    text = re.sub(r'(?i)(cr|crore|crores|lakh|lakhs|mn|million|bn|billion|k)s?$', '', text).strip()

    # Remove commas (handles both Western 1,234 and Indian 1,23,456)
    text = text.replace(',', '')

    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return None


# ── Pass 1: Table scan ─────────────────────────────────────────────────────

def _match_kpi(cell_text: str) -> Optional[Tuple[str, str]]:
    """
    Return (canonical_name, category) if cell_text matches any alias.
    Normalise whitespace and newlines before matching.
    Exclude cells that are clearly not KPI labels (too long, total-and-liabilities, etc.)
    """
    clean = re.sub(r'\s+', ' ', cell_text.strip())
    if not clean or len(clean) > 200:
        return None
    # Exclude "Total Equity and Liabilities" — this is a balance sheet foot total,
    # not the equity line. Would match "Total Equity" alias incorrectly.
    if re.search(r'total\s+equity\s+and\s+liabilit', clean, re.IGNORECASE):
        return None
    for name, cat, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(clean):
                return name, cat
    return None


def _extract_kpis_from_tables(tables: List[Dict[str, Any]]) -> List[Dict]:
    """
    Scan every table row.

    Key improvement over v2: checks columns 0, 1, and 2 for the KPI label.
    Indian annual reports often have an indent column leaving col 0 empty,
    with the label in col 1. This was the primary cause of zero table hits.

    Deduplication: if the same canonical KPI appears multiple times across
    tables, keep the one from the earliest page (primary statement).
    """
    found: Dict[str, Dict] = {}  # canonical_name → best hit

    for table_info in tables:
        page = table_info["page"]
        rows = table_info["data"]
        if not rows:
            continue

        for row in rows:
            if not row:
                continue

            # Try columns 0, 1, 2 as the label column
            label_col = None
            match = None
            for col_idx in range(min(3, len(row))):
                cell = str(row[col_idx] or "").strip()
                if not cell:
                    continue
                m = _match_kpi(cell)
                if m:
                    label_col = col_idx
                    match = m
                    break

            if match is None:
                continue

            kpi_name, category = match

            # Look for first valid numeric value in columns AFTER the label column
            value = None
            raw_value = ""
            for cell in row[label_col + 1:]:
                cell_str = str(cell or "").strip()
                v = _parse_number(cell_str)
                if v is not None:
                    value = v
                    raw_value = cell_str
                    break

            if value is None:
                continue

            # Keep earliest-page occurrence (primary statement > notes)
            if kpi_name not in found or page < found[kpi_name]["page"]:
                label_text = str(row[label_col] or "")
                source = f"Table p.{page}: {' | '.join(str(c or '')[:30] for c in row[:6])}"
                found[kpi_name] = {
                    "name": kpi_name,
                    "category": category,
                    "raw_value": raw_value,
                    "value": value,
                    "page": page,
                    "source": source,
                    "from_table": True,
                }

    result = list(found.values())
    logger.info(f"Table scan found {len(result)} KPIs")
    return result


# ── Pass 1b: Line-pair text scan ───────────────────────────────────────────

def _extract_kpis_from_text_lines(pages: List) -> List[Dict]:
    """
    Scan PyMuPDF page text for label+value pairs in Indian annual reports.

    Scoring strategy:
    - Pages where 4+ different KPI labels appear are financial statement pages
      (P&L, Balance Sheet). Their values are preferred over scattered narrative mentions.
    - Within financial statement pages, the value immediately following the label
      (skipping note reference numbers) is taken as the current-year value.
    - For non-statement pages, values are only accepted if they are plausibly large
      (> 100 for monetary KPIs) to filter out percentages and growth rates.
    """
    note_num_re = re.compile(r'^\d{1,2}[A-Za-z]?$')

    RATIO_KPIs = {'ratio', '%', 'per share', 'eps', 'margin',
                  'return on', 'coverage', 'turnover', 'roe', 'roa', 'roce'}

    def is_ratio_kpi(name: str) -> bool:
        return any(kw in name.lower() for kw in RATIO_KPIs)

    # ── Pass A: score each page by KPI label density ───────────────────────
    page_kpi_counts: Dict[int, int] = {}
    for page in pages:
        count = 0
        for line in page.text.splitlines():
            clean = re.sub(r'\s+', ' ', line.strip())
            if clean and _match_kpi(clean):
                count += 1
        page_kpi_counts[page.page_number] = count

    # Financial statement pages: 3+ KPI labels on the same page
    fs_pages = {pn for pn, cnt in page_kpi_counts.items() if cnt >= 3}

    # ── Pass B: extract values, scoring by page type ───────────────────────
    # collected: {kpi_name: [(value, page_num, is_fs_page, raw, source)]}
    collected: Dict[str, List] = {}

    for page in pages:
        pn = page.page_number
        is_fs = pn in fs_pages
        lines = [ln.strip() for ln in page.text.splitlines()]

        for i, line in enumerate(lines):
            if not line:
                continue
            clean = re.sub(r'\s+', ' ', line)
            m = _match_kpi(clean)
            if m is None:
                continue

            kpi_name, category = m
            value = None
            raw_value = ""
            source = ""

            # Same line: "Revenue from Operations  1,31,336  1,13,176"
            # or multi-column: "EBITDA  74,163  8.7  1,83,422  21.5"
            # Strategy: collect ALL numeric tokens on the line, prefer the largest
            # (consolidated is typically the largest value on multi-column lines)
            parts = re.split(r'\s{2,}', line)
            if len(parts) > 1:
                all_values = []
                for part in parts[1:]:
                    stripped = part.strip()
                    if note_num_re.match(stripped.replace(',', '')):
                        continue
                    v = _parse_number(stripped)
                    if v is not None:
                        all_values.append((v, stripped))
                if all_values:
                    if is_fs and not is_ratio_kpi(kpi_name) and len(all_values) > 1:
                        # Financial statement multi-column: take the largest
                        value, raw_value = max(all_values, key=lambda x: abs(x[0]))
                    else:
                        value, raw_value = all_values[0]
                    source = f"Text p.{pn}: {line[:100]}"

            # Next lines — on FS pages, collect all consecutive number lines and take largest
            if value is None:
                consecutive_values = []
                for j in range(i + 1, min(i + 6, len(lines))):
                    nl = lines[j].strip()
                    if not nl:
                        continue
                    if note_num_re.match(nl.replace(',', '')):
                        continue  # skip note ref numbers
                    if not re.search(r'\d', nl):
                        break   # pure text line — stop looking
                    v = _parse_number(nl.split()[0])
                    if v is not None:
                        consecutive_values.append((v, nl.split()[0], nl[:60]))
                    else:
                        break  # non-numeric line ends the sequence

                if consecutive_values:
                    if is_fs and not is_ratio_kpi(kpi_name) and len(consecutive_values) > 1:
                        # Multi-value sequence on FS page: take largest (consolidated)
                        best_v = max(consecutive_values, key=lambda x: abs(x[0]))
                        value, raw_value = best_v[0], best_v[1]
                        source = f"Text p.{pn}: {line} → {best_v[2]}"
                    else:
                        value, raw_value = consecutive_values[0][0], consecutive_values[0][1]
                        source = f"Text p.{pn}: {line} → {consecutive_values[0][2]}"

            if value is None:
                continue

            # Filter: skip sub-1 for monetary KPIs
            if not is_ratio_kpi(kpi_name) and abs(value) < 1.0:
                continue

            # Filter: on non-statement pages, skip small monetary values
            # (likely percentages, growth rates, segment counts)
            if not is_fs and not is_ratio_kpi(kpi_name) and abs(value) < 100:
                continue

            if kpi_name not in collected:
                collected[kpi_name] = []
            collected[kpi_name].append((value, pn, is_fs, raw_value, source, category))

    # ── Pass C: choose best candidate per KPI ─────────────────────────────
    found: Dict[str, Dict] = {}
    for kpi_name, candidates in collected.items():
        # Prefer financial statement page candidates
        fs_candidates = [c for c in candidates if c[2]]  # is_fs=True
        pool = fs_candidates if fs_candidates else candidates

        if not pool:
            continue

        if is_ratio_kpi(kpi_name):
            # Ratios: earliest page in pool
            best = min(pool, key=lambda c: c[1])
        else:
            # Monetary: largest absolute value in pool
            best = max(pool, key=lambda c: abs(c[0]))

        value, pn, _, raw_value, source, category = best
        found[kpi_name] = {
            "name": kpi_name,
            "category": category,
            "raw_value": raw_value,
            "value": value,
            "page": pn,
            "source": source,
            "from_table": False,
        }

    result = list(found.values())
    logger.info(f"Text line scan found {len(result)} KPIs "
                f"({len(fs_pages)} financial-statement pages detected)")
    return result


# ── Pass 2: LLM extraction ─────────────────────────────────────────────────

def _llm_extract_kpis(text_chunks: List[str], currency: str, unit_scale: str) -> List[Dict]:
    """
    Ask the LLM to find KPI values in narrative text.
    Prioritises chunks that mention numeric values (financial highlights, MD&A).
    """
    # Filter to chunks likely to contain financial figures
    number_re = re.compile(r'\b\d[\d,]*(?:\.\d+)?')
    financial_chunks = [c for c in text_chunks if number_re.search(c)]
    if not financial_chunks:
        financial_chunks = text_chunks

    combined = "\n\n---\n\n".join(financial_chunks[:30])

    prompt = f"""You are a financial analyst extracting KPIs from an Indian annual report.

Currency: {currency}   Unit scale: {unit_scale}

RULES:
- Extract ONLY values that EXPLICITLY appear in the text. Do NOT calculate or invent.
- For Indian reports: "crore" = 10 million, "lakh" = 100,000
- Prefer current year values over prior year comparatives when both present.
- Common Indian phrasings: "Revenue from Operations", "Profit for the year",
  "Total Comprehensive Income", "Finance Costs", "Other Income"

Text:
{combined}

Return JSON with key "kpis" — an array where each item has:
  "name": one of the exact canonical names listed below (skip if none fit)
  "value": float (current year value only)
  "source_text": exact quote from text (max 150 chars)
  "page_hint": page number if visible, else null

Canonical names to look for:
{chr(10).join(f'  - {n}' for n in KPI_NAMES)}

Include only items where value is clearly stated in the text."""

    try:
        data = chat_complete_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
        )
        items = data.get("kpis", [])
        if not isinstance(items, list):
            return []
        logger.info(f"LLM extracted {len(items)} KPI candidates")
        return items
    except Exception as e:
        logger.error(f"LLM KPI extraction failed: {e}")
        return []


# ── Pass 3: Verification ───────────────────────────────────────────────────

def _verify_kpi(kpi_name: str, value: float, all_kpis: List[Dict]) -> Tuple[bool, str]:
    """Basic sanity checks — arithmetic relationships between KPIs."""
    lookup: Dict[str, float] = {
        k["name"]: k["value"] for k in all_kpis if k.get("value") is not None
    }

    def get(fragment: str) -> Optional[float]:
        for k, v in lookup.items():
            if fragment.lower() in k.lower():
                return v
        return None

    pat = get("profit after tax") or get("net profit")
    liabilities = get("total liabilities")
    equity = get("total equity") or get("net worth")

    # Revenue should be > net profit (unless it's a ratio/percentage)
    if "revenue" in kpi_name.lower() and "%" not in kpi_name:
        if pat is not None and abs(pat) > 0 and value < abs(pat):
            return False, f"Revenue ({value:,.0f}) < Net Profit ({pat:,.0f}) — unit mismatch?"

    # Assets ≈ Liabilities + Equity (within 5%)
    if "total assets" in kpi_name.lower() and liabilities is not None and equity is not None:
        reconstructed = liabilities + equity
        if reconstructed > 0 and abs(reconstructed - value) / reconstructed > 0.05:
            return False, f"Assets ({value:,.0f}) ≠ Liabilities ({liabilities:,.0f}) + Equity ({equity:,.0f})"

    return True, "Passed sanity checks"


# ── Main entry point ───────────────────────────────────────────────────────

def extract_kpis(
    tables: List[Dict[str, Any]],
    text_chunks: List[str],
    currency: str = "INR",
    unit_scale: str = "crores",
    pages: Optional[List] = None,
) -> List[ExtractedKPI]:
    """Full three-pass KPI extraction with verification."""
    logger.info(f"KPI extraction: {len(tables)} tables, {len(text_chunks)} text chunks, {len(pages or [])} pages")

    # Pass 1a — table scan (label in cols 0/1/2)
    table_kpis = _extract_kpis_from_tables(tables)

    # Pass 1b — line-pair text scan (label and value on adjacent lines in raw text)
    text_line_kpis = _extract_kpis_from_text_lines(pages) if pages else []

    # Merge passes 1a + 1b — table wins over text-line for same KPI
    merged: Dict[str, Dict] = {}
    for k in text_line_kpis:
        merged[k["name"]] = k
    for k in table_kpis:
        merged[k["name"]] = k  # table overwrites text-line

    found_names = set(merged.keys())

    # Pass 2 — LLM for anything still missing
    missing = [n for n in KPI_NAMES if n not in found_names]
    if missing and text_chunks:
        llm_kpis = _llm_extract_kpis(text_chunks, currency, unit_scale)
    else:
        llm_kpis = []

    for k in llm_kpis:
        name = k.get("name")
        if not name or name not in KPI_NAMES:
            continue
        try:
            val = float(k["value"]) if k.get("value") is not None else None
        except (TypeError, ValueError):
            continue
        if val is not None and name not in merged:
            merged[name] = {
                "name": name,
                "category": KPI_CATEGORY.get(name, "Other"),
                "value": val,
                "page": k.get("page_hint"),
                "source": k.get("source_text", ""),
                "from_table": False,
            }

    # Pass 3 — verify
    all_list = list(merged.values())
    results = []
    for kpi_data in all_list:
        name = kpi_data.get("name", "")
        value = kpi_data.get("value")
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        is_verified, note = _verify_kpi(name, value, all_list)
        category = kpi_data.get("category") or KPI_CATEGORY.get(name, "Other")

        results.append(ExtractedKPI(
            name=name,
            value=value,
            unit=unit_scale,
            currency=currency,
            page_number=kpi_data.get("page"),
            source_text=str(kpi_data.get("source", ""))[:500],
            is_verified=is_verified,
            verification_note=note,
            category=category,
        ))

    verified = sum(1 for r in results if r.is_verified)
    logger.info(f"KPI extraction complete: {len(results)} KPIs ({verified} verified)")
    return results
