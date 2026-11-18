"""
KPI cleansing: turn the rule-based extractor's raw KPI rows into a consistent,
analysis-ready table. Every change is logged so the notebook can show an audit
trail (rule, KPI, old value → new value, reason).

Steps
  1. Unit detection per report    — reports state "₹ in lakh / million / crore";
                                    the extractor stored everything as "crores".
  2. Scale normalisation          — convert monetary KPIs to ₹ crore.
  3. Unit typing                  — ratios / per-share / % KPIs get their own unit.
  4. Sign convention              — CapEx outflows stored as positive amounts.
  5. Stale-copy detection         — identical value to the prior year's report.
  6. Accounting consistency       — share-of-revenue bounds, PAT vs PBT, and ratios
                                    recomputed from their components (fixes %-scaled
                                    values, derives missing ratios = imputation).
  7. Domain range checks          — physically impossible values → NaN.
"""
import re
from collections import Counter
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# ── Unit detection ───────────────────────────────────────────────────────────

_UNIT_RE = re.compile(
    # "₹ in lakh", "(in ₹ crore)", "Amount in crore", "All amounts are in millions of Indian Rupee"
    r"(?:(?:₹|rs\.?|inr|amounts?)\s*(?:are\s+)?(?:in\s*)?(?:₹\s*|rs\.?\s*)?|\(\s*in\s*(?:₹\s*)?)"
    r"(crores?|cr\b|lakhs?|lacs?|millions?|mn\b|billions?|bn\b|thousands?|'000s?\b)"   # banks: "(₹ in '000)"
    r"|\(\s*(000)'?s\s+omitted\s*\)",                                                     # SBI: "(000s omitted)"
    re.IGNORECASE,
)
_TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "billion": 100.0, "thousand": 1e-4}


def _canon_unit(token: str) -> str:
    t = token.lower()
    if t.startswith("cr"):
        return "crore"
    if t.startswith(("lakh", "lac")):
        return "lakh"
    if t.startswith(("million", "mn")):
        return "million"
    if t.startswith(("billion", "bn")):
        return "billion"
    return "thousand"


def detect_report_unit(page_texts: List[str]) -> Tuple[str, Dict[str, int]]:
    """Most frequent '₹ in <unit>' declaration across a report's pages."""
    counts: Counter = Counter()
    for text in page_texts:
        counts.update(_canon_unit(a or b) for a, b in _UNIT_RE.findall(text))
    unit = counts.most_common(1)[0][0] if counts else "crore"
    return unit, dict(counts)


def detect_report_unit_with_fallback(
    statement_pages: List[str], all_pages: List[str], min_evidence: int = 10
) -> Tuple[str, Dict[str, int], str]:
    """
    Prefer the unit declared on financial-statement pages (narrative sections
    often quote figures in a different unit); fall back to the whole report
    when statements carry too few declarations. Returns (unit, counts, scope).
    """
    unit, counts = detect_report_unit(statement_pages)
    if sum(counts.values()) >= min_evidence:
        return unit, counts, "statements"
    unit, counts = detect_report_unit(all_pages)
    return unit, counts, "whole_report"


# ── KPI typing ───────────────────────────────────────────────────────────────

RATIO_KPIS = {"Current Ratio", "Debt-to-Equity Ratio", "Interest Coverage Ratio"}
PERCENT_KPIS = {"Return on Capital Employed (ROCE) %", "Return on Equity (ROE) %", "EBITDA Margin %",
                "Net Profit Margin %"}
PER_SHARE_KPIS = {"Earnings Per Share (EPS)", "Dividend Per Share", "Book Value Per Share"}

# Plausible ranges for non-monetary KPIs (Indian listed companies)
DOMAIN_RANGES = {
    "Current Ratio": (0.0, 50.0),
    "Debt-to-Equity Ratio": (0.0, 30.0),
    "Interest Coverage Ratio": (-100.0, 1000.0),
    "Earnings Per Share (EPS)": (-5000.0, 20000.0),
    "Dividend Per Share": (0.0, 5000.0),
    "Book Value Per Share": (-5000.0, 50000.0),
    "Return on Capital Employed (ROCE) %": (-100.0, 200.0),
}


# (kpi, min share, max share, explanation) of Total Revenue, by absolute value
SHARE_OF_REVENUE_RULES = [
    ("Revenue from Operations", 0.5, 1.001, "must be 50–100% of Total Revenue; likely a growth % or note number"),
    ("Other Income", 0.0, 0.5, "Other Income cannot dominate Total Revenue"),
    ("EBITDA", 0.01, 1.0, "EBITDA this small vs revenue is a misread (margin % or note ref)"),
    ("Finance Costs", 0.0, 0.5, "Finance costs above half of revenue are implausible"),
]

# ratio = numerator / denominator — used to verify, fix and derive ratios
RATIO_COMPONENTS = [
    ("Current Ratio", "Current Assets", "Current Liabilities"),
    ("Debt-to-Equity Ratio", "Debt (Total Borrowings)", "Total Equity / Shareholders Equity"),
]


def kpi_unit(name: str) -> str:
    if name in RATIO_KPIS:
        return "x"
    if name in PERCENT_KPIS or name.endswith("%"):
        return "%"
    if name in PER_SHARE_KPIS:
        return "₹/share"
    return "₹ crore"


# ── Cleaning ─────────────────────────────────────────────────────────────────

def clean_kpis(raw: pd.DataFrame, report_units: Dict[str, str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    raw: kpis_raw.csv rows (name, value, report_id, company, fiscal_year, …)
    report_units: {report_id: "crore" | "lakh" | "million" | …}
    Returns (clean_df, audit_log_df).
    """
    df = raw.copy()
    df["value_raw"] = df["value"]
    log: List[dict] = []

    def record(i, rule, new, reason):
        log.append({
            "rule": rule, "company": df.at[i, "company"], "fiscal_year": df.at[i, "fiscal_year"],
            "kpi": df.at[i, "name"], "old": df.at[i, "value"], "new": new, "reason": reason,
        })
        df.at[i, "value"] = new

    # 1–3. unit typing + scale normalisation to ₹ crore
    df["unit"] = df["name"].map(kpi_unit)
    df["source_unit"] = df["report_id"].map(report_units).fillna("crore")
    for i in df.index:
        if df.at[i, "unit"] != "₹ crore" or pd.isna(df.at[i, "value"]):
            continue
        factor = _TO_CRORE[df.at[i, "source_unit"]]
        if factor != 1.0:
            record(i, "scale", round(df.at[i, "value"] * factor, 2),
                   f"report states ₹ in {df.at[i, 'source_unit']} → ₹ crore (×{factor:g})")

    # 4. sign convention — CapEx is reported as a cash outflow (negative) in cash-flow statements
    for i in df.index[df["name"] == "Capital Expenditure (CapEx)"]:
        v = df.at[i, "value"]
        if pd.notna(v) and v < 0:
            record(i, "sign", abs(v), "cash-flow outflow sign dropped; CapEx stored as a positive amount")

    # 5. stale copies: identical monetary value to the same company's other year
    for _, g in df[df["unit"] == "₹ crore"].groupby(["company", "name"]):
        if g["fiscal_year"].nunique() < 2:
            continue
        prev = None
        for i in g.sort_values("fiscal_year").index:
            v = df.at[i, "value"]
            if prev is not None and pd.notna(v) and v == prev and abs(v) > 1:
                record(i, "stale_copy", np.nan, "identical to prior year — extractor read the comparative column")
            prev = v

    # 6. accounting consistency, per report
    derived_rows: List[dict] = []
    for _, idx in df.groupby("report_id").groups.items():
        g = df.loc[idx]
        val = dict(zip(g["name"], g["value"]))
        row = {n: i for i, n in zip(g.index, g["name"])}
        tot = val.get("Total Revenue")

        # 6a. line items that must be a bounded share of Total Revenue
        if pd.notna(tot) and tot > 0:
            for name, lo, hi, why in SHARE_OF_REVENUE_RULES:
                v = val.get(name)
                if pd.notna(v) and not (lo * tot <= abs(v) <= hi * tot):
                    record(row[name], "consistency", np.nan,
                           f"{why} (is {abs(v) / tot:.1%} of Total Revenue {tot:,.0f})")
                    val[name] = np.nan

        # 6b. PBT vs PAT — a positive PAT cannot exceed PBT by 2×; revenue decides which is wrong
        pbt, pat = val.get("Profit Before Tax (PBT)"), val.get("Profit After Tax (PAT) / Net Profit")
        if pd.notna(pbt) and pd.notna(pat) and pat > 0 and pbt < 0.5 * pat:
            if pd.notna(tot) and tot > 0 and pat > 0.35 * tot:
                record(row["Profit After Tax (PAT) / Net Profit"], "consistency", np.nan,
                       f"PAT ({pat:,.0f}) > 2× PBT and implausibly {pat / tot:.0%} of revenue")
            else:
                record(row["Profit Before Tax (PBT)"], "consistency", np.nan,
                       f"PBT ({pbt:,.0f}) far below PAT ({pat:,.0f}); wrong row picked")

        tl, ta = val.get("Total Liabilities"), val.get("Total Assets")
        if pd.notna(tl) and pd.notna(ta) and ta > 0 and tl < 0.01 * ta:
            record(row["Total Liabilities"], "consistency", np.nan,
                   f"<1% of Total Assets ({ta:,.0f}); wrong row picked")

        # 6c. ratios: recompute from components; fix %-scaled values; derive missing ones
        for ratio, num, den in RATIO_COMPONENTS:
            n, d = val.get(num), val.get(den)
            if not (pd.notna(n) and pd.notna(d) and d > 0):
                continue
            recomputed = n / d
            stored = val.get(ratio)
            if ratio not in row:
                r0 = df.loc[g.index[0]]
                derived_rows.append({
                    **{c: r0[c] for c in ("report_id", "company", "sector", "fiscal_year", "source_unit")},
                    "name": ratio, "value": round(recomputed, 4), "value_raw": np.nan, "unit": "x",
                    "is_verified": 0, "category": "Ratios",
                })
                log.append({"rule": "derived", "company": r0["company"], "fiscal_year": r0["fiscal_year"],
                            "kpi": ratio, "old": np.nan, "new": round(recomputed, 4),
                            "reason": f"missing — derived as {num} / {den}"})
            elif pd.notna(stored) and abs(stored / 100 - recomputed) < 0.15 * recomputed:
                record(row[ratio], "recompute", round(stored / 100, 4),
                       f"stored as a percentage — {num}/{den} = {recomputed:.2f}")
            elif pd.isna(stored) or abs(stored - recomputed) > 0.25 * recomputed:
                record(row[ratio], "recompute", round(recomputed, 4),
                       f"disagrees with {num}/{den} = {recomputed:.2f}")

    if derived_rows:
        df = pd.concat([df, pd.DataFrame(derived_rows)], ignore_index=True)

    # 7. domain ranges (last, so recomputed ratios are validated too)
    for i in df.index:
        lo_hi = DOMAIN_RANGES.get(df.at[i, "name"])
        v = df.at[i, "value"]
        if lo_hi and pd.notna(v) and not (lo_hi[0] <= v <= lo_hi[1]):
            record(i, "domain_range", np.nan, f"outside plausible range {lo_hi}")

    df["is_clean"] = df["value"].notna()
    return df, pd.DataFrame(log)


def iqr_outliers(values: pd.Series, k: float = 1.5) -> pd.Series:
    """Tukey IQR rule on log10(|x|) — financial values span orders of magnitude."""
    logv = np.log10(values.abs().replace(0, np.nan))
    q1, q3 = logv.quantile(0.25), logv.quantile(0.75)
    iqr = q3 - q1
    return (logv < q1 - k * iqr) | (logv > q3 + k * iqr)
