"""
Footnote & Consistency Engine  (flagship module)
─────────────────────────────────────────────────
Cross-checks:
  1. Footnote vs. Narrative  — figures/disclosures in notes differ from body
  2. Prior-year promise tracking — what management said vs. what they did
  3. Contingent liabilities     — quantified and unquantified exposures
  4. Related-party transactions  — unusual patterns
  5. Off-balance-sheet items    — commitments, guarantees, leases

Each flag is scored and ranked so the user sees the most material items first.
"""
import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from loguru import logger

from app.core.config import settings
from app.core.llm_client import chat_complete_json
from app.db.models import FlagSeverity


@dataclass
class FootnoteFlagResult:
    flag_type: str
    title: str
    description: str
    severity: FlagSeverity
    footnote_text: str
    narrative_text: str
    prior_year_text: str
    page_number: Optional[int]
    ranking_score: float = 0.0


# ── Pattern-based pre-scan helpers ────────────────────────────────────────

CONTINGENT_PATTERNS = re.compile(
    r"contingent\s+liabilit|claim\s+not\s+acknowledged|disputed\s+tax|"
    r"pending\s+litigat|show\s+cause\s+notice|demand\s+under\s+appeal",
    re.IGNORECASE,
)

RELATED_PARTY_PATTERNS = re.compile(
    r"related\s+party|related-party|key\s+managerial\s+personnel|kmp|"
    r"subsidiary|associate\s+company|group\s+compan",
    re.IGNORECASE,
)

OFF_BALANCE_PATTERNS = re.compile(
    r"off.balance.sheet|operating\s+lease|capital\s+commitment|"
    r"guarantee\s+given|letter\s+of\s+credit|bank\s+guarantee",
    re.IGNORECASE,
)

PROMISE_PATTERNS = re.compile(
    r"we\s+(plan|intend|aim|expect|will|shall)\s+to|"
    r"going\s+forward|in\s+the\s+coming\s+year|"
    r"(capex|expansion|plant|capacity)\s+(of|plan|target)",
    re.IGNORECASE,
)


def _extract_footnote_sections(pages: List) -> Tuple[str, int]:
    """
    Find notes-to-accounts section. Returns (text, start_page).
    """
    notes_patterns = re.compile(
        r"notes\s+(forming\s+part\s+of|to\s+(the\s+)?)"
        r"(financial\s+statements|accounts)",
        re.IGNORECASE,
    )
    collecting = False
    texts = []
    start_page = None

    for page in pages:
        if notes_patterns.search(page.text[:300]):
            collecting = True
            start_page = page.page_number
        if collecting:
            texts.append(page.text)
            if len(texts) > 60:   # cap footnote section at 60 pages
                break

    return "\n\n".join(texts), start_page or 0


def _extract_narrative_section(pages: List) -> str:
    """
    Extract the main body narrative (MDA + financial highlights, excluding footnotes).
    """
    narrative_patterns = re.compile(
        r"management.{0,10}discussion|financial\s+(highlights|review|performance)",
        re.IGNORECASE,
    )
    texts = []
    for page in pages:
        if narrative_patterns.search(page.text[:300]):
            texts.append(page.text)
        if len(texts) > 30:
            break
    return "\n\n".join(texts)


def _find_prior_year_promises(prior_year_text: str) -> List[str]:
    """Extract forward-looking statements from the prior year filing text."""
    sentences = re.split(r'(?<=[.!?])\s+', prior_year_text)
    promises = [s.strip() for s in sentences if PROMISE_PATTERNS.search(s)]
    return promises[:20]  # top 20


def _llm_cross_check_footnotes(footnote_text: str, narrative_text: str) -> List[Dict]:
    """LLM pass: find inconsistencies between footnotes and narrative."""
    fn_excerpt = footnote_text[:6000]
    narr_excerpt = narrative_text[:3000]

    prompt = f"""You are an expert financial auditor analyzing an annual report.

NARRATIVE (from MD&A / Financial Highlights):
{narr_excerpt}

FOOTNOTES / NOTES TO ACCOUNTS:
{fn_excerpt}

Identify specific inconsistencies, discrepancies, or items where:
1. A figure in the footnotes differs from the narrative
2. The footnotes disclose something material not mentioned in the narrative
3. Contingent liabilities or legal claims that appear significant
4. Related-party transactions that look unusual
5. Off-balance-sheet commitments or guarantees

For each finding return:
- "flag_type": one of: inconsistency / contingent_liability / related_party / off_balance_sheet / disclosure_gap
- "title": short title (max 12 words)
- "description": explanation of why this is notable (80-200 words)
- "severity": low / medium / high / critical
- "footnote_excerpt": relevant excerpt from footnotes (max 300 chars)
- "narrative_excerpt": relevant excerpt from narrative (max 300 chars)

Return JSON object with key "flags" containing array of findings.
Only report findings with clear textual evidence."""

    try:
        data = chat_complete_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        return data.get("flags", [])
    except Exception as e:
        logger.error(f"LLM footnote cross-check failed: {e}")
        return []


def _llm_check_prior_year_promises(promises: List[str], current_year_text: str) -> List[Dict]:
    """Check if prior-year commitments were fulfilled in the current year."""
    if not promises:
        return []

    promises_text = "\n".join(f"- {p}" for p in promises[:10])
    current_excerpt = current_year_text[:5000]

    prompt = f"""An annual report from the PRIOR year made the following forward-looking statements:

{promises_text}

Below is text from the CURRENT year's annual report:
{current_excerpt}

For each prior-year promise, determine if it was:
1. Fulfilled — evidence in current year text
2. Not mentioned — no reference found
3. Explicitly not fulfilled — current year admits it wasn't done
4. Partially fulfilled

Return JSON with key "checks", array of:
- "promise": the original promise (max 150 chars)
- "status": fulfilled / not_mentioned / not_fulfilled / partial
- "evidence": supporting text from current year (max 200 chars)
- "severity": low / medium / high"""

    try:
        data = chat_complete_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        return data.get("checks", [])
    except Exception as e:
        logger.error(f"Prior-year promise check failed: {e}")
        return []


def _score_flag(flag_type: str, severity: str) -> float:
    """Compute a ranking score for a flag (higher = surface first)."""
    severity_weights = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
    type_weights = {
        "contingent_liability": 1.2,
        "inconsistency": 1.1,
        "off_balance_sheet": 1.0,
        "related_party": 0.9,
        "not_fulfilled": 1.1,
        "partial": 0.7,
        "disclosure_gap": 0.8,
    }
    s = severity_weights.get(severity, 0.5)
    t = type_weights.get(flag_type, 0.6)
    return round(s * t, 3)


def run_footnote_engine(
    pages: List,
    prior_year_pages: Optional[List] = None,
) -> List[FootnoteFlagResult]:
    """
    Main entry point for the Footnote & Consistency Engine.

    Args:
        pages: current year document pages
        prior_year_pages: prior year document pages (for promise tracking)

    Returns:
        Ranked list of FootnoteFlagResult
    """
    logger.info("Running Footnote & Consistency Engine")

    footnote_text, fn_start_page = _extract_footnote_sections(pages)
    narrative_text = _extract_narrative_section(pages)

    all_flags: List[FootnoteFlagResult] = []

    # ── 1. Cross-check footnotes vs. narrative ─────────────────────────────
    if footnote_text and narrative_text:
        raw_flags = _llm_cross_check_footnotes(footnote_text, narrative_text)
        for f in raw_flags:
            severity_str = f.get("severity", "medium")
            try:
                severity = FlagSeverity(severity_str)
            except ValueError:
                severity = FlagSeverity.MEDIUM

            flag_type = f.get("flag_type", "inconsistency")
            score = _score_flag(flag_type, severity_str)

            all_flags.append(FootnoteFlagResult(
                flag_type=flag_type,
                title=f.get("title", "Unnamed Flag"),
                description=f.get("description", ""),
                severity=severity,
                footnote_text=f.get("footnote_excerpt", ""),
                narrative_text=f.get("narrative_excerpt", ""),
                prior_year_text="",
                page_number=fn_start_page,
                ranking_score=score,
            ))

    # ── 2. Prior-year promise tracking ─────────────────────────────────────
    if prior_year_pages:
        prior_full_text = " ".join(p.text for p in prior_year_pages[:50])
        promises = _find_prior_year_promises(prior_full_text)
        current_full_text = " ".join(p.text for p in pages[:50])
        checks = _llm_check_prior_year_promises(promises, current_full_text)

        for c in checks:
            status = c.get("status", "not_mentioned")
            if status in ("not_fulfilled", "partial", "not_mentioned"):
                severity_str = c.get("severity", "medium")
                try:
                    severity = FlagSeverity(severity_str)
                except ValueError:
                    severity = FlagSeverity.MEDIUM

                score = _score_flag(status, severity_str)
                all_flags.append(FootnoteFlagResult(
                    flag_type="prior_year_promise",
                    title=f"Prior-year commitment: {status.replace('_', ' ')}",
                    description=(
                        f"Prior-year statement: \"{c.get('promise', '')}\"\n"
                        f"Status: {status}. {c.get('evidence', '')}"
                    ),
                    severity=severity,
                    footnote_text="",
                    narrative_text=c.get("evidence", ""),
                    prior_year_text=c.get("promise", ""),
                    page_number=None,
                    ranking_score=score,
                ))

    # ── 3. Pattern-based quick flags ───────────────────────────────────────
    for page in pages:
        if CONTINGENT_PATTERNS.search(page.text):
            # These are already handled by LLM above if in footnotes,
            # but flag any page we missed
            matched = CONTINGENT_PATTERNS.search(page.text)
            if matched:
                excerpt = page.text[max(0, matched.start()-100):matched.end()+200]
                # Only add if not already covered
                already = any(
                    "contingent" in f.flag_type or "contingent" in f.title.lower()
                    for f in all_flags
                )
                if not already:
                    all_flags.append(FootnoteFlagResult(
                        flag_type="contingent_liability",
                        title="Contingent liability disclosure",
                        description="Potential contingent liability detected in footnotes/notes.",
                        severity=FlagSeverity.MEDIUM,
                        footnote_text=excerpt[:300],
                        narrative_text="",
                        prior_year_text="",
                        page_number=page.page_number,
                        ranking_score=_score_flag("contingent_liability", "medium"),
                    ))
                    break

    # ── Sort by ranking score (descending) ─────────────────────────────────
    all_flags.sort(key=lambda x: x.ranking_score, reverse=True)
    logger.info(f"Footnote engine produced {len(all_flags)} flags")
    return all_flags
