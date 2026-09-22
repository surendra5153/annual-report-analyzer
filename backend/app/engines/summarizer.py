"""
Section-wise summarization engine.

Speed optimisation (v2):
- All section LLM calls are fired concurrently via ThreadPoolExecutor.
  With 6 sections each taking ~2s, sequential = 12s, concurrent = ~2-3s.
  The GIL is released during I/O (HTTP to Gemini), so threads actually run
  in parallel here.
"""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from dataclasses import dataclass

from loguru import logger

from app.core.config import settings
from app.core.llm_client import chat_complete

SECTION_PATTERNS = {
    "business_overview": [
        r"business\s+overview", r"company\s+overview", r"about\s+us",
        r"our\s+business", r"corporate\s+overview",
    ],
    "mda": [
        r"management.{0,10}discussion", r"md\s*&\s*a", r"management.{0,10}analysis",
        r"review\s+of\s+operations",
    ],
    "financial_highlights": [
        r"financial\s+highlights", r"financial\s+summary", r"key\s+financials",
        r"financial\s+performance", r"financial\s+results",
    ],
    "outlook": [
        r"outlook", r"future\s+prospects", r"way\s+forward",
        r"strategic\s+priorities", r"guidance",
    ],
    "risk_factors": [
        r"risk\s+factors", r"risks\s+and\s+concerns", r"risk\s+management",
    ],
    "footnotes": [
        r"notes\s+to\s+(the\s+)?accounts", r"notes\s+to\s+(the\s+)?financial\s+statements",
        r"significant\s+accounting\s+policies", r"contingent\s+liabilities",
    ],
}

SECTION_LABELS = {
    "business_overview":   "Business Overview",
    "mda":                 "Management Discussion & Analysis (MD&A)",
    "financial_highlights":"Financial Highlights",
    "outlook":             "Outlook & Future Prospects",
    "risk_factors":        "Risk Factors",
    "footnotes":           "Notes to Accounts / Footnotes",
}


@dataclass
class SectionResult:
    section_name: str
    summary: str
    raw_text: str
    start_page: Optional[int]
    end_page: Optional[int]


def _detect_sections(pages: List) -> Dict[str, Dict]:
    """Heuristically map pages to sections using heading patterns."""
    sections: Dict[str, Dict] = {
        s: {"start_page": None, "end_page": None, "texts": []}
        for s in SECTION_PATTERNS
    }
    for page in pages:
        page_num = page.page_number
        # Search the first 800 chars — headings are near the top of the page
        snippet = page.text[:800].lower()
        for section_name, patterns in SECTION_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, snippet):
                    sec = sections[section_name]
                    if sec["start_page"] is None:
                        sec["start_page"] = page_num
                    sec["end_page"] = page_num
                    sec["texts"].append(page.text)
                    break
    return sections


def _summarize_one(section_name: str, raw_text: str) -> str:
    """Single section summary — called concurrently."""
    label = SECTION_LABELS.get(section_name, section_name.replace("_", " ").title())
    truncated = raw_text[:8000]
    prompt = (
        f'Summarize the following "{label}" section from an annual report.\n'
        "Be concise (150-300 words). Highlight the most important facts, figures, and trends.\n"
        "Do not add information not present in the text.\n\n"
        f"Text:\n{truncated}\n\nSummary:"
    )
    try:
        return chat_complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
    except Exception as e:
        logger.error(f"Summarization failed for {section_name}: {e}")
        return f"[Summarization failed: {e}]"


def summarize_document(pages: List) -> List[SectionResult]:
    """
    Detect sections then summarize all of them concurrently.
    """
    logger.info("Detecting and summarizing document sections")
    section_map = _detect_sections(pages)

    # Only process sections that actually have content
    active = {
        name: info
        for name, info in section_map.items()
        if info["texts"]
    }

    if not active:
        logger.info("No recognisable sections found — skipping summarization")
        return []

    logger.info(f"Summarising {len(active)} sections concurrently: {list(active.keys())}")

    results: List[SectionResult] = []

    # Fire all LLM calls in parallel — each is pure I/O (HTTP request to Gemini)
    with ThreadPoolExecutor(max_workers=min(len(active), 6)) as pool:
        future_to_name = {
            pool.submit(
                _summarize_one,
                name,
                "\n\n".join(info["texts"]),
            ): (name, info)
            for name, info in active.items()
        }

        for future in as_completed(future_to_name):
            name, info = future_to_name[future]
            try:
                summary = future.result()
            except Exception as e:
                summary = f"[Summarization failed: {e}]"

            raw_text = "\n\n".join(info["texts"])
            results.append(SectionResult(
                section_name=name,
                summary=summary,
                raw_text=raw_text,
                start_page=info["start_page"],
                end_page=info["end_page"],
            ))
            logger.info(
                f"Summarised: {name} "
                f"(pp. {info['start_page']}–{info['end_page']})"
            )

    return results
