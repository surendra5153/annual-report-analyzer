"""Unit tests for the local ML layer (no network, no models, no DB)."""
import math

import pandas as pd
import pytest

from app.ml.bm25 import BM25
from app.ml.fusion import reciprocal_rank_fusion
from app.ml.kpi_clean import clean_kpis, detect_report_unit_with_fallback, kpi_unit
from app.ml.label_pages import label_document
from app.ml.text_clean import clean_document, normalize_unicode


# ── Retrieval ────────────────────────────────────────────────────────────────

def test_bm25_ranks_exact_term_first():
    docs = ["revenue grew strongly", "EBITDA margin improved", "dividend of Rs 8 per share"]
    top = BM25(docs).top_k("what was the EBITDA margin", 3)
    assert top[0][0] == 1
    assert all(score > 0 for _, score in top)


def test_bm25_unknown_query_returns_nothing():
    assert BM25(["a b c"]).top_k("zzz", 5) == []


def test_rrf_rewards_agreement_between_rankings():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]])
    assert fused[0] == "a"            # rank 1 + rank 2 beats everything else
    assert set(fused) == {"a", "b", "c", "d"}


def test_citation_parser_handles_model_formats():
    from app.engines.rag_qa import _cited_indices
    text = "According to [Source 3], x [1, 2] y [Sources 4 and 5] z [9]"
    assert _cited_indices(text, 6) == [1, 2, 3, 4, 5]
    # header copied verbatim, and bare "Source N" without brackets
    assert _cited_indices("[Source 1 | HAL · FY2026 · amounts in ₹ lakh | Page 36] and **Source 6**", 6) == [1, 6]


# ── Text cleaning ────────────────────────────────────────────────────────────

def test_normalize_unicode_fixes_legacy_rupee_and_ligatures():
    out = normalize_unicode("(` in Lakhs) proﬁt – Rs.500 Board’s")
    assert out == "(₹ in Lakhs) profit - ₹500 Board's"


def test_clean_document_removes_running_header_and_page_numbers_only_at_edges():
    body = "Particulars\nNote\n27\n2025\nRevenue from opera-\ntions\n1,203.73\nOther income\n3.53\nTotal"
    pages = [f"Acme Annual Report 2025\nStatement of Profit and Loss\n{body}\nsection {i}\nfootnote\n{i}" for i in range(1, 6)]
    res = clean_document(pages)
    assert "Annual Report" not in res.pages[0]   # running header removed
    assert "27\n2025" in res.pages[0]            # mid-page numbers are table cells, kept
    assert "operations" in res.pages[0]          # lowercase hyphen break joined
    assert not res.pages[0].rstrip().endswith("1")  # trailing page number removed


def test_label_document_carries_narrative_sections_forward():
    pages = ["Management Discussion and Analysis\nindustry", "more narrative", "Balance Sheet as at 31 March", "x"]
    labels = [l for l, _ in label_document(pages)]
    assert labels[:3] == ["mda", "mda", "balance_sheet"]


# ── KPI cleansing ────────────────────────────────────────────────────────────

def _kpis(rows, report="r1", company="Co", year=2025):
    return pd.DataFrame([{"name": n, "value": v, "report_id": report, "company": company, "sector": "X",
                          "fiscal_year": year, "is_verified": 1, "category": "c"} for n, v in rows])


def test_unit_detection_prefers_statements_then_falls_back():
    assert detect_report_unit_with_fallback(["(₹ in Lakhs)"] * 12, ["₹ crore"] * 50)[0] == "lakh"
    assert detect_report_unit_with_fallback([], ["₹ in Million"] * 3)[0] == "million"


def test_kpi_unit_typing():
    assert kpi_unit("Current Ratio") == "x"
    assert kpi_unit("Earnings Per Share (EPS)") == "₹/share"
    assert kpi_unit("Total Revenue") == "₹ crore"


def test_scale_normalisation_lakh_to_crore():
    clean, log = clean_kpis(_kpis([("Total Revenue", 3354645.0), ("Current Ratio", 1.5)]), {"r1": "lakh"})
    v = dict(zip(clean.name, clean.value))
    assert v["Total Revenue"] == pytest.approx(33546.45)
    assert v["Current Ratio"] == 1.5           # ratios are never rescaled


def test_consistency_rejects_misread_revenue_and_fixes_percent_ratio():
    rows = [("Total Revenue", 1000.0), ("Revenue from Operations", 4.89),
            ("Debt (Total Borrowings)", 105.0), ("Total Equity / Shareholders Equity", 31.0),
            ("Debt-to-Equity Ratio", 335.0)]
    clean, log = clean_kpis(_kpis(rows), {"r1": "crore"})
    v = dict(zip(clean.name, clean.value))
    assert math.isnan(v["Revenue from Operations"])
    assert v["Debt-to-Equity Ratio"] == pytest.approx(3.35)
    assert {"consistency", "recompute"} <= set(log.rule)


def test_missing_ratio_is_derived_from_components():
    clean, log = clean_kpis(_kpis([("Current Assets", 200.0), ("Current Liabilities", 100.0)]), {"r1": "crore"})
    assert dict(zip(clean.name, clean.value))["Current Ratio"] == pytest.approx(2.0)
    assert "derived" in set(log.rule)


def test_stale_copy_from_prior_year_is_rejected():
    df = pd.concat([_kpis([("Operating Cash Flow", 17183.27)], "r1", year=2025),
                    _kpis([("Operating Cash Flow", 17183.27)], "r2", year=2026)])
    clean, _ = clean_kpis(df.reset_index(drop=True), {"r1": "crore", "r2": "crore"})
    assert math.isnan(clean[clean.report_id == "r2"].value.iloc[0])
