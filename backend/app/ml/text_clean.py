"""
Text cleansing for annual-report pages.

Raw PyMuPDF text from Indian annual reports carries a lot of noise:
  * running headers / footers repeated on every page ("Annual Report 2025-26",
    company name, section title)
  * bare page numbers
  * typographic ligatures (ﬁ, ﬂ) and look-alike characters (– — −, Rs. / `)
  * words hyphenated across line breaks
  * ragged whitespace

`clean_document` removes these and returns per-page statistics so the
before/after effect of every step can be measured in the preprocessing notebook.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

# How many lines at the top/bottom of a page are header/footer candidates
_EDGE_LINES = 3
# A line is "running" if it appears at a page edge on at least this share of pages
_REPEAT_THRESHOLD = 0.30

_PAGE_NUMBER_RE = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.IGNORECASE)
# Join only when the continuation is lowercase: "opera-\ntions" → "operations",
# but keep real compounds like "Single-\nLocation"
_HYPHEN_BREAK_RE = re.compile(r"([a-z])-\n([a-z])")
_DASHES_RE = re.compile(r"[‐‑‒–—―−]")
_SQUOTES_RE = re.compile(r"[‘’‚‛′]")
_DQUOTES_RE = re.compile(r"[“”„″]")
_RUPEE_RE = re.compile(r"(?<![A-Za-z])(Rs\.?|INR)\s?(?=\d)")
# Legacy "Rupee Foradian" font maps the ₹ glyph to a backtick: "(` in Lakhs)", "` 140.50 crore"
_BACKTICK_RUPEE_RE = re.compile(r"`(?=\s*(?:in\b|\d|crores?\b|lakhs?\b|millions?\b|nil\b))", re.IGNORECASE)
# Other legacy rupee fonts print ₹ as a capital letter: TCS "(H crore)", HDFC Bank "(C in '000)" / "CC in crore",
# Wipro "(I in millions, except…", Airtel "J 5 each".
# Only rewritten inside a unit declaration — "(X in <unit>" or a line that starts with it — never in ordinary text.
_UNIT_WORDS = r"(?:crores?|lakhs?|millions?|billions?|thousands?|'000s?)\b"
_LETTER_RUPEE_UNIT_RE = re.compile(rf"(?:\(\s*[HJCI]|(?m:^[ \t]*C{{1,2}}))\s+(?=(?i:(?:in\s+)?{_UNIT_WORDS}))")   # Bajaj: "(H In Crore)"
_SPACES_RE = re.compile(r"[ \t ]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass
class CleanStats:
    chars_before: int = 0
    chars_after: int = 0
    header_footer_lines: int = 0
    page_number_lines: int = 0
    hyphen_joins: int = 0
    unicode_fixes: int = 0


@dataclass
class CleanResult:
    pages: List[str]
    stats: List[CleanStats]
    running_lines: List[str] = field(default_factory=list)


def _line_key(line: str) -> str:
    """Normalise a line so "Annual Report 2025-26 | 14" and "... | 15" compare equal."""
    return re.sub(r"\d+", "#", line.strip().lower())


def normalize_unicode(text: str) -> str:
    """NFKC (ligatures → letters, full-width → ASCII), unified dashes/quotes and rupee notation."""
    text = unicodedata.normalize("NFKC", text)
    text = _DASHES_RE.sub("-", text)
    text = _SQUOTES_RE.sub("'", text)
    text = _DQUOTES_RE.sub('"', text)
    text = _BACKTICK_RUPEE_RE.sub("₹", text)
    text = _LETTER_RUPEE_UNIT_RE.sub(lambda m: "(₹ " if m.group(0).lstrip().startswith("(") else "₹ ", text)
    text = _RUPEE_RE.sub("₹", text)
    return text


def find_running_lines(pages: List[str]) -> Counter:
    """Count, per normalised line, how many pages have it in their top/bottom edge."""
    counts: Counter = Counter()
    for page in pages:
        lines = [l for l in page.splitlines() if l.strip()]
        edge = lines[:_EDGE_LINES] + lines[-_EDGE_LINES:]
        counts.update({_line_key(l) for l in edge if len(l.strip()) < 120})
    return counts


def clean_document(pages: List[str]) -> CleanResult:
    """Clean all pages of one report (running-line detection needs the whole document)."""
    n_pages = max(len(pages), 1)
    counts = find_running_lines(pages)
    running = {k for k, c in counts.items() if c / n_pages >= _REPEAT_THRESHOLD and k.strip("# ")}

    cleaned, stats = [], []
    for raw in pages:
        st = CleanStats(chars_before=len(raw))

        text = normalize_unicode(raw)
        st.unicode_fixes = sum(1 for a, b in zip(raw, text) if a != b) + abs(len(raw) - len(text))

        kept = []
        lines = text.splitlines()
        non_blank = [i for i, l in enumerate(lines) if l.strip()]
        edge_idx = set(non_blank[:_EDGE_LINES] + non_blank[-_EDGE_LINES:])
        for i, line in enumerate(lines):
            # Only edge lines: bare numbers mid-page are table cells (note refs, years)
            if i in edge_idx and line.strip() and _PAGE_NUMBER_RE.match(line):
                st.page_number_lines += 1
                continue
            if i in edge_idx and _line_key(line) in running:
                st.header_footer_lines += 1
                continue
            kept.append(line)
        text = "\n".join(kept)

        st.hyphen_joins = len(_HYPHEN_BREAK_RE.findall(text))
        text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
        text = _SPACES_RE.sub(" ", text)
        text = "\n".join(l.strip() for l in text.splitlines())
        text = _BLANK_LINES_RE.sub("\n\n", text).strip()

        st.chars_after = len(text)
        cleaned.append(text)
        stats.append(st)

    return CleanResult(pages=cleaned, stats=stats, running_lines=sorted(running))


# ── Page-level numeric features ──────────────────────────────────────────────

_NUMBER_RE = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")


def page_features(text: str) -> Dict[str, float]:
    """Cheap structural features used in EDA and by the page classifier."""
    lines = [l for l in text.splitlines() if l.strip()]
    numbers = _NUMBER_RE.findall(text)
    n_chars = len(text)
    numeric_lines = sum(1 for l in lines if _NUMBER_RE.fullmatch(l.strip().replace(" ", "")))
    return {
        "n_chars": n_chars,
        "n_words": len(text.split()),
        "n_lines": len(lines),
        "n_numbers": len(numbers),
        "digit_ratio": round(sum(c.isdigit() for c in text) / n_chars, 4) if n_chars else 0.0,
        "numeric_line_ratio": round(numeric_lines / len(lines), 4) if lines else 0.0,
        "avg_line_len": round(sum(map(len, lines)) / len(lines), 2) if lines else 0.0,
        "has_rupee": int("₹" in text),
    }
