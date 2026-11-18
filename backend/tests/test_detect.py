"""
Upload-detection tests: page 1 decides whether a PDF is an annual report,
and confidence is computed from evidence rather than self-reported by the LLM.
The LLM is monkeypatched, so these run without Ollama.
"""
import pytest

import app.core.llm_client as llm_client
from app.api.routes import filings
from app.api.routes.filings import _detect_metadata_from_text, _first_page, _subject_from_first_page

COVER_LETTER = """Reliance Industries Limited
Date: August 1, 2025
To, BSE Limited, Phiroze Jeejeebhoy Towers
Sub: Annual Report for the Financial Year 2024-25
Dear Sir/Madam, pursuant to Regulation 34 of SEBI (LODR) Regulations..."""

AGM_NOTICE = """NOTICE
Notice is hereby given that the 48th Annual General Meeting of the members
of Example Limited will be held on Friday, 29 August 2025 at 10:00 a.m."""

# Enough distinct signals (annual report, balance sheet, P&L, cash flow, auditor...) to be "strong"
STRONG_BODY = ("Annual Report 2024-25 Board's Report Balance Sheet Statement of Profit and Loss "
               "Cash Flow Independent Auditor's Report financial year ₹ crore")
WEAK_BODY = "cash flow for the financial year"


@pytest.mark.parametrize("text,expected", [
    (COVER_LETTER, True),
    ("Sub: Submission of Annual Report under\nRegulation 34 of SEBI LODR", True),
    ("Subject: Outcome of Board Meeting\nheld on 12 May 2025", False),
    ("INTEGRATED ANNUAL REPORT 2023-24\nGrowing responsibly", True),
    ("Form 10-K\nAnnual report pursuant to section 13", True),
    (AGM_NOTICE, False),
    ("", False),
])
def test_subject_from_first_page(text, expected):
    assert _subject_from_first_page(text)[1] is expected


def test_subject_wraps_onto_second_line():
    subject, ok = _subject_from_first_page("Sub: Submission of the\nAnnual Report for FY 2024-25\nDear Sir")
    assert ok and "Annual Report" in subject


def test_first_page_skips_image_only_cover():
    assert _first_page(["", "  \n", COVER_LETTER]) == COVER_LETTER
    assert _first_page([]) == ""


def _fake_llm(page1_answer):
    """chat_complete_json stub: page-1 classifier gets *page1_answer*, metadata call gets fixed fields."""
    def fake(messages, **kw):
        if "FIRST PAGE" in messages[0]["content"]:
            if isinstance(page1_answer, Exception):
                raise page1_answer
            return page1_answer
        return {"company_name": "Example Limited", "fiscal_year": 2025}
    return fake


@pytest.mark.parametrize("pages,page1_answer,accepted,confidence", [
    ([COVER_LETTER, STRONG_BODY], None, True, "high"),                       # regex yes + strong
    ([COVER_LETTER, WEAK_BODY], None, True, "medium"),                       # regex yes only
    (["Corporate overview " * 10, STRONG_BODY], {"subject": "Overview", "is_annual_report": False}, True, "medium"),
    (["Corporate overview " * 10, WEAK_BODY], {"subject": "Brochure", "is_annual_report": True}, True, "medium"),
    ([AGM_NOTICE, WEAK_BODY], {"subject": "Notice of AGM", "is_annual_report": False}, False, None),
    ([AGM_NOTICE, WEAK_BODY], RuntimeError("ollama down"), True, "low"),
])
def test_detect_decision_and_confidence(monkeypatch, pages, page1_answer, accepted, confidence):
    monkeypatch.setattr(llm_client, "chat_complete_json", _fake_llm(page1_answer))
    r = _detect_metadata_from_text(pages, page_count=10)
    assert r.is_financial_report is accepted
    if accepted:
        assert r.confidence == confidence
        # A '… Limited' header line on the pages beats the LLM's name
        assert r.company_name == ("Reliance Industries Limited" if pages[0] == COVER_LETTER else "Example Limited")
    else:
        assert "Notice of AGM" in r.rejection_reason


def test_regex_hit_skips_page1_llm_call(monkeypatch):
    calls = []
    def fake(messages, **kw):
        calls.append(messages[0]["content"])
        return {}
    monkeypatch.setattr(llm_client, "chat_complete_json", fake)
    filings._detect_metadata_from_text([COVER_LETTER, STRONG_BODY], page_count=10)
    assert not any("FIRST PAGE" in c for c in calls)
