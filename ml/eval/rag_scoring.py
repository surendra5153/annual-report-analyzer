"""
Scoring for the Q&A evaluation (notebook 05).

An answer is free text such as "Total income was **₹1,00,365.08 crore** [2]".
We parse every amount it states, convert it with its unit, and compare with
the gold value.

Metrics per answer
  numeric_correct   some stated figure equals the gold value (±0.5% relative;
                    ±0.01 abs for per-share; ±tolerance pp for percentages).
                    Signs are ignored: "a loss of ₹2.38 lakh" = −2.38.
  unit_correct      the matching figure carries a unit that makes it correct
                    (₹ amount with lakh/crore/million…, "%" for percentages)
  unsupported       figures in the answer that appear in NONE of the sources the
                    model was given → fabricated / unverifiable numbers
  cited             at least one [n] citation resolved
  refused           the answer says the information is not in the report
"""
import re
from typing import Dict, List

TO_CRORE = {"crore": 1.0, "cr": 1.0, "lakh": 0.01, "lac": 0.01, "million": 0.1, "mn": 0.1, "billion": 100.0, "bn": 100.0,
            "thousand": 1e-4}

# A number may not start inside a word or right after "-"/"/" (so "FY2024-25" is not read as 202 and -25)
_NUM = r"(?<![\w.,/\-])\(?-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?\)?(?![\d,])"
_AMOUNT_RE = re.compile(
    rf"(₹|rs\.?|inr)?\s?({_NUM})\s?(crores?|cr\b|lakhs?|lacs?|millions?|mn\b|billions?|bn\b|thousands?)?\s?(%|per share)?",
    re.IGNORECASE,
)
_REFUSAL_RE = re.compile(r"not (?:found|available|mentioned|provided|disclosed|contain|present|stated|reported|specified)"
                         r"|no (?:information|data|mention|details)|does not (?:contain|mention|provide|include|have)"
                         r"|cannot (?:find|be found|determine)|unable to (?:find|determine|locate)", re.IGNORECASE)


def _to_float(s: str) -> float:
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-") or s.startswith("(-")
    return -abs(float(s.strip("()").replace(",", "").lstrip("-"))) if neg else float(s.strip("()").replace(",", ""))


def parse_figures(text: str) -> List[Dict]:
    """[{value, unit, rupee, percent, per_share, raw}] for every number in the text."""
    out = []
    for m in _AMOUNT_RE.finditer(text):
        rupee, num, unit, suffix = m.group(1), m.group(2), (m.group(3) or "").lower(), (m.group(4) or "").lower()
        try:
            v = _to_float(num)
        except ValueError:
            continue
        unit = re.sub(r"s$", "", unit) if unit not in ("cr", "mn", "bn") else unit
        out.append({"value": v, "unit": unit or None, "rupee": bool(rupee), "percent": suffix == "%",
                    "per_share": suffix == "per share", "raw": m.group(0).strip()})
    return out


def _close(a: float, b: float, rel: float = 0.005, abs_tol: float = 0.0) -> bool:
    a, b = abs(a), abs(b)
    return abs(a - b) <= max(rel * max(b, 1e-9), abs_tol)


def score_numeric(answer: str, q: Dict, report_unit: str) -> Dict:
    figs = parse_figures(answer)
    kind, gold = q["kind"], q["value"]
    numeric, unit_ok = False, False
    for f in figs:
        if kind == "percent":
            if _close(f["value"], gold, rel=0, abs_tol=q.get("tolerance", 0.3)):
                numeric = True
                unit_ok = unit_ok or f["percent"]
        elif kind == "ratio":                     # computed ratios, e.g. current ratio 2.61×
            if _close(f["value"], gold, rel=0, abs_tol=q.get("tolerance", 0.02)):
                numeric = unit_ok = True
        elif kind == "per_share":
            if _close(f["value"], gold, rel=0.005, abs_tol=0.01):
                numeric = True
                unit_ok = unit_ok or f["rupee"] or f["per_share"]
        else:  # amount: compare in ₹ crore
            gold_cr = gold * TO_CRORE[report_unit]
            if f["unit"] in TO_CRORE:
                if _close(f["value"] * TO_CRORE[f["unit"]], gold_cr):
                    numeric = unit_ok = True
            elif not f["percent"] and _close(f["value"], gold):  # right number, no unit stated
                numeric = True
    return {"numeric_correct": numeric, "unit_correct": unit_ok}


def _digits(s: str) -> str:
    return re.sub(r"[,\s]", "", s)


_PAGE_REF = re.compile(r"\b(?:pages?|p\.)\s?\d+(?:\s?[-–]\s?\d+)?", re.IGNORECASE)


def _source_numbers(sources_text: str, cap: int = 400) -> List[float]:
    vals = []
    for f in parse_figures(sources_text):
        v = abs(f["value"])
        if v >= 0.01 and not (1990 <= v <= 2035 and float(v).is_integer()):
            vals.append(v)
    return sorted(set(vals))[:cap]


def _derivable(v: float, nums: List[float]) -> bool:
    """v is a unit conversion of a source number, or a % change / difference / sum of two."""
    v = abs(v)
    for a in nums:
        for k in (0.01, 0.1, 10.0, 100.0, 1e-4):        # lakh↔crore, million↔crore, …
            if _close(v, a * k, rel=0.005):
                return True
    for i, a in enumerate(nums):
        for b in nums[i + 1:]:
            if _close(v, abs(a - b) / b * 100, rel=0, abs_tol=0.05) or _close(v, abs(a - b) / a * 100, rel=0, abs_tol=0.05):
                return True
            if _close(v, abs(a - b), rel=0.001) or _close(v, a + b, rel=0.001):
                return True
    return False


def unsupported_figures(answer: str, sources_text: str) -> List[str]:
    """
    Figures stated in the answer that cannot be traced to the sources: neither present
    (digit-string match, commas ignored) nor derivable from source numbers (unit conversion,
    % change, difference or sum of two) — so legitimate calculations are not counted as fabrication.
    """
    src = _digits(sources_text)
    nums = None
    bad = []
    answer = _PAGE_REF.sub(" ", answer)              # "page 392", "p.216" are citations, not figures
    for f in parse_figures(answer):
        token = _digits(f["raw"])
        num = re.sub(r"[^\d.]", "", token)
        if not num or num.count(".") > 1:
            continue
        v = abs(f["value"])
        if v < 10 and "." not in num:          # small integers: list numbering, "[3]", "2 years"
            continue
        if 1990 <= v <= 2035 and "." not in num:  # years
            continue
        core = num.rstrip("0").rstrip(".") if "." in num else num
        if core and core not in src and num not in src:
            nums = nums if nums is not None else _source_numbers(sources_text)
            if not _derivable(f["value"], nums):
                bad.append(f["raw"])
    return bad


def is_refusal(answer: str) -> bool:
    return bool(_REFUSAL_RE.search(answer))
