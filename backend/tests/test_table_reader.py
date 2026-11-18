"""
Table-reader tests. Pure-function tests always run; the real-page tests run
when the uploaded annual reports are present locally (skipped otherwise).
"""
import os
import sqlite3
from pathlib import Path

import pytest

from app.ml.table_reader import (_fiscal_year, _merge_split_numbers, extra_qualifiers, parse_number, question_item, question_year,
                                 read_tables, render_answer, ReaderResult)


# ── Pure functions ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("tok,expected", [
    ("1,00,365.08", 100365.08), ("(1,116.49)", -1116.49), ("-1002959", -1002959.0), ("2,109,728", 2109728.0),
    ("-", None), ("Notes", None),
])
def test_parse_number(tok, expected):
    assert parse_number(tok) == expected


@pytest.mark.parametrize("tok,year", [("2026", 2026), ("2025-26", 2026), ("FY25", None), ("2024,", 2024), ("31", None),
                                      ("31.03.2026", 2026), ("31/03/2025", 2025), ("30.09.2025", 2026)])
def test_fiscal_year_tokens(tok, year):
    assert _fiscal_year(tok) == year


def test_question_item_disambiguates_pbt_and_profit():
    assert question_item("What was the consolidated profit before tax for FY 2025-26?") == "profit before tax"
    assert question_item("What was the standalone profit for the year FY 2024-25?") == "profit for the year"
    assert question_item("What was the diluted earnings per share for FY 2025-26?") == "diluted eps"


def test_question_year():
    assert question_year("total income for FY 2024-25?", 2026) == 2025
    assert question_year("total assets as at 31 March 2026?", 2025) == 2026
    assert question_year("What was the revenue?", 2026) == 2026


def test_extra_qualifiers_block_unanswerable_and_narrower_questions():
    assert extra_qualifiers("What was the revenue from operations in Antarctica?", "revenue from operations") == ["antarctica"]
    assert "attributable" in extra_qualifiers("What was the profit attributable to owners of the parent?", "profit")
    assert extra_qualifiers("By what percentage did consolidated total income grow in FY 2025-26?", "total income") == []


def test_split_thousands_are_rejoined():
    # TCS font: "9,453" comes out as the words "9" and "453" with no comma; real separate cells stay apart
    line = [(74, 0, 89, 8, "Lease"), (441, 0, 445.5, 8, "9"), (446, 0, 458, 8, "453"), (521, 0, 540, 8, "7,838")]
    assert [w[4] for w in _merge_split_numbers(line)] == ["Lease", "9,453", "7,838"]
    assert [w[4] for w in _merge_split_numbers([(400, 0, 405, 8, "9"), (450, 0, 462, 8, "453")])] == ["9", "453"]


@pytest.mark.parametrize("text,unit", [("(H crore)", "crore"), ("(C in '000)", "thousand"), ("(J in lakhs)", "lakh"),
                                       ("₹ in '000s", "thousand"), ("(000s omitted)", "thousand"),
                                       ("(I in millions, except per share data)", "million"), ("CC in crore", "crore")])
def test_letter_rupee_glyph_units(text, unit):
    from app.ml.kpi_clean import detect_report_unit
    from app.ml.text_clean import normalize_unicode
    assert detect_report_unit([normalize_unicode(text)]) == (unit, {unit: 1})


def test_heading_kind_needs_a_real_heading():
    from app.ml.statement_index import heading_kind
    assert heading_kind("Consolidated Balance Sheet\n(₹ crore)\nAs at") == "balance_sheet"
    assert heading_kind("STANDALONE PROFIT AND LOSS ACCOUNT\nFor the year ended March 31, 2026") == "profit_loss"
    assert heading_kind("comprise the Standalone Balance Sheet as at March 31, 2026, and") is None
    assert heading_kind("SCHEDULES TO THE STANDALONE BALANCE SHEET\nAs at March 31, 2026") is None
    assert heading_kind("320\nS TA N D A L O N E B A L A N C E S H E E T\nAs at March 31, 2025") == "balance_sheet"
    assert heading_kind("158\nStatement of Profit and Loss (Contd.)\n(₹ In Crore)") == "profit_loss"
    assert heading_kind("Outstanding \namounts \ncarried in the \nBalance Sheet\nTransaction") is None   # wrapped column header


def test_render_answer_with_change_and_crore_equivalent():
    res = ReaderResult(True, item="total income", label="Total Income", value=1207.26, prior=1750.65, year=2026,
                       prior_year=2025, change_pct=(1207.26 - 1750.65) / 1750.65 * 100, unit="lakh",
                       scope="standalone", page=57, kind="profit_loss")
    text = render_answer(res)
    assert "₹1,207.26 lakh (≈ ₹12.07 crore)" in text
    assert "down **31.04%**" in text
    assert "FY 2025-26" in text and "page 57" in text


# ── Real statement pages (local data) ────────────────────────────────────────

DB = Path(__file__).resolve().parents[1] / "annual_reports.db"


def _pdf(filing_id: str):
    if not DB.exists():
        return None
    row = sqlite3.connect(DB).execute("select file_path from filings where id=?", (filing_id,)).fetchone()
    path = row and row[0]
    if path and not os.path.isabs(path):
        path = str(DB.parent / path)
    return path if path and os.path.exists(path) else None


def _row(tables, label):
    for t in tables:
        for r in t.rows:
            if r.label.lower().startswith(label.lower()) and r.values:
                return t, r
    raise AssertionError(f"row {label!r} not found")


def test_hal_consolidated_pl_ungrouped_lakh_numbers():
    pdf = _pdf("9820853e-5875-42a8-8001-2ad123f1b432")
    if not pdf:
        pytest.skip("HAL report not available")
    t, r = _row(read_tables(pdf, 321), "Total Income")
    assert t.years == [2026, 2025] and t.unit == "lakh"
    assert r.values == {2026: 3678795.0, 2025: 3354264.0}
    _, neg = _row(read_tables(pdf, 321), "Changes in Inventories")
    assert neg.values[2026] == -1002959.0


def test_adani_comparative_columns_and_parenthesised_negatives():
    pdf = _pdf("9a88fab0-2586-44d2-b151-c9c65e144db9")
    if not pdf:
        pytest.skip("Adani FY25 report not available")
    tables = read_tables(pdf, 392)
    _, r = _row(tables, "Total Income")
    assert r.values == {2025: 100365.08, 2024: 98281.51}
    _, ex = _row(tables, "Add / (Less) : Exceptional")
    assert ex.values[2024] == -715.37


def test_airtel_two_statements_on_one_spread():
    pdf = _pdf("8566cb3c-d316-44fb-9636-7c2f391c6f48")
    if not pdf:
        pytest.skip("Airtel report not available")
    tables = read_tables(pdf, 216)
    assert len(tables) == 2                              # balance sheet panel + P&L panel
    _, other = _row(tables, "Other income")
    assert other.values == {2026: 28173.0, 2025: 15737.0}
    _, total = _row(tables, "Total income")              # unlabelled total, named from its section
    assert total.values[2026] == 2137901.0
