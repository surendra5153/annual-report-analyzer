"""
Weak (rule-based) page-type labels for the PageClassifier dataset.

Annual reports print a section heading near the top of the page. We search the
first `_TOP_CHARS` characters of each cleaned page for heading patterns and take
the earliest match. Narrative sections (MD&A, Directors' report, …) only show
the heading on their first page, so their label is carried forward until the
next heading. `label_source` records whether a label came from a heading or
was carried — hand-corrected labels later get `label_source = "gold"`.
"""
import re
from typing import List, Optional, Tuple

_TOP_CHARS = 600

LABELS = [
    "balance_sheet",
    "profit_loss",
    "cash_flow",
    "equity_changes",
    "notes",
    "auditor_report",
    "directors_report",
    "mda",
    "corporate_governance",
    "other",
]

_HEADINGS = {
    "balance_sheet": r"balance\s+sheet\s+as\s+at",
    "profit_loss": r"statement\s+of\s+profit\s*(?:and|&)\s*loss",
    "cash_flow": r"(?:statement\s+of\s+cash\s+flows?|cash\s+flow\s+statement)",
    "equity_changes": r"statement\s+of\s+changes\s+in\s+equity",
    "notes": r"notes\s+(?:to|forming\s+part\s+of)\s+(?:the\s+)?(?:standalone\s+|consolidated\s+)?financial\s+statements",
    "auditor_report": r"independent\s+auditor'?s?'?\s+report",
    "directors_report": r"(?:directors'?\s*report|board'?s'?\s+report)",
    "mda": r"management\s+discussion\s*(?:and|&)\s*analysis",
    "corporate_governance": r"(?:report\s+on\s+)?corporate\s+governance\s+report|report\s+on\s+corporate\s+governance",
}
_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in _HEADINGS.items()}

# Sections whose heading appears only on the first page
_CARRY_FORWARD = {"notes", "auditor_report", "directors_report", "mda", "corporate_governance"}
_MAX_CARRY_PAGES = 40


def heading_label(text: str) -> Optional[str]:
    top = text[:_TOP_CHARS]
    hits = [(m.start(), label) for label, rx in _COMPILED.items() if (m := rx.search(top))]
    return min(hits)[1] if hits else None


def scope_of(text: str) -> str:
    top = text[:_TOP_CHARS].lower()
    if "consolidated" in top:
        return "consolidated"
    if "standalone" in top:
        return "standalone"
    return "unknown"


def label_document(pages: List[str]) -> List[Tuple[str, str]]:
    """Return [(label, label_source)] for every page of one report."""
    out: List[Tuple[str, str]] = []
    current, carried = None, 0
    for text in pages:
        label = heading_label(text)
        if label:
            current, carried = label, 0
            out.append((label, "heading"))
        elif current in _CARRY_FORWARD and carried < _MAX_CARRY_PAGES and text.strip():
            carried += 1
            out.append((current, "carry"))
        else:
            current = None
            out.append(("other", "default"))
    return out
