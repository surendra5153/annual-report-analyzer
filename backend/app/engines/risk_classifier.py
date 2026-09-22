"""
Risk Classification Engine.
Identifies and categorizes risk disclosures from annual reports into:
financial, regulatory, cybersecurity, climate, supply_chain, operational, other.
"""
import json
from typing import List
from dataclasses import dataclass

from loguru import logger

from app.core.config import settings
from app.core.llm_client import chat_complete_json
from app.db.models import RiskCategory, FlagSeverity

RISK_KEYWORDS = {
    RiskCategory.FINANCIAL: [
        "credit risk", "liquidity risk", "interest rate", "currency risk",
        "market risk", "impairment", "write-off", "bad debt", "npa",
    ],
    RiskCategory.REGULATORY: [
        "regulatory", "compliance", "legal proceedings", "litigation",
        "penalty", "government policy", "sebi", "rbi", "taxation",
    ],
    RiskCategory.CYBERSECURITY: [
        "cyber", "data breach", "information security", "ransomware",
        "it risk", "digital risk", "data privacy",
    ],
    RiskCategory.CLIMATE: [
        "climate", "environmental", "esg", "carbon", "emission",
        "sustainability", "water scarcity", "natural disaster",
    ],
    RiskCategory.SUPPLY_CHAIN: [
        "supply chain", "procurement", "vendor", "raw material",
        "logistics", "geopolitical", "import", "export",
    ],
    RiskCategory.OPERATIONAL: [
        "operational risk", "key personnel", "talent", "employee",
        "manufacturing", "capacity", "technology obsolescence",
    ],
}


@dataclass
class ClassifiedRisk:
    category: RiskCategory
    title: str
    description: str
    severity: FlagSeverity
    page_number: int
    source_text: str


def _classify_risks_with_llm(text_chunks: List[str]) -> List[ClassifiedRisk]:
    """Use LLM to extract and classify risks from text."""
    combined = "\n\n---\n\n".join(text_chunks[:15])

    prompt = f"""You are an expert financial analyst. Extract all risk disclosures from the following annual report text.

For each risk, provide:
- "category": one of: financial, regulatory, cybersecurity, climate, supply_chain, operational, other
- "title": short title (max 10 words)
- "description": clear description of the risk (50-150 words)
- "severity": one of: low, medium, high, critical
- "source_text": exact quote from text where this risk is described (max 200 chars)

Text:
{combined}

Return a JSON object with key "risks" containing an array of risk objects.
Only include risks explicitly mentioned in the text."""

    try:
        data = chat_complete_json(
            messages=[{"role": "user", "content": prompt}],
        )
        risks_raw = data.get("risks", [])
        results = []
        for r in risks_raw:
            try:
                results.append(ClassifiedRisk(
                    category=RiskCategory(r.get("category", "other")),
                    title=r.get("title", "Unknown Risk"),
                    description=r.get("description", ""),
                    severity=FlagSeverity(r.get("severity", "medium")),
                    page_number=r.get("page_number", 0),
                    source_text=r.get("source_text", ""),
                ))
            except (ValueError, KeyError):
                continue
        return results
    except Exception as e:
        logger.error(f"Risk classification failed: {e}")
        return []


def _keyword_prescan(text: str) -> List[str]:
    """Quickly identify which risk category keywords appear in the text."""
    text_lower = text.lower()
    found = []
    for category, keywords in RISK_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(category)
    return found


def classify_risks(pages: List, risk_section_text: str = "") -> List[ClassifiedRisk]:
    """
    Classify risks from the full document.
    Prioritizes the dedicated risk section, falls back to full scan.
    """
    logger.info("Classifying risks")

    # Use the risk section if detected, otherwise scan all pages
    if risk_section_text:
        relevant_chunks = [risk_section_text[i:i+2000] for i in range(0, min(len(risk_section_text), 16000), 2000)]
    else:
        relevant_chunks = []
        for page in pages:
            if _keyword_prescan(page.text):
                relevant_chunks.append(page.text)
        relevant_chunks = relevant_chunks[:20]

    if not relevant_chunks:
        logger.warning("No risk-related content found in document")
        return []

    risks = _classify_risks_with_llm(relevant_chunks)
    logger.info(f"Classified {len(risks)} risks")
    return risks
