"""
KPI cleansing for the live pipeline.

Runs the same rules as notebook 01 (app/ml/kpi_clean.py) on a filing's
freshly extracted KPIs:
  * detect the report's reporting unit (₹ crore / lakh / million …) from its
    financial-statement pages,
  * normalise monetary KPIs to ₹ crore, type ratios / % / per-share KPIs,
  * reject values that break accounting identities or domain ranges,
  * recompute / derive ratios from their components,
  * reject values copied from the company's prior-year report.

Raw values are kept in `KPI.raw_value` (+ `source_unit`), so the step is
idempotent and Q&A can still match figures as printed in the report.
"""
from typing import Dict, List

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import Company, Filing, KPI
from app.ml.kpi_clean import clean_kpis, detect_report_unit_with_fallback, kpi_unit
from app.ml.page_classifier import classify_pages, STATEMENT_TYPES
from app.ml.text_clean import normalize_unicode

CLEAN_UNITS = {"₹ crore", "x", "%", "₹/share"}
DERIVED_SOURCE = "Derived from extracted components"
_UNIT_TO_FILING_SCALE = {"crore": "crores", "lakh": "lakhs", "million": "millions", "billion": "billions", "thousand": "thousands"}


def detect_unit(page_texts: List[str]) -> Dict:
    norm = [normalize_unicode(t) for t in page_texts]
    labels = classify_pages(page_texts)
    statements = [t for t, l in zip(norm, labels) if l in STATEMENT_TYPES]
    unit, counts, scope = detect_report_unit_with_fallback(statements, norm)
    return {"unit": unit, "counts": counts, "evidence_from": scope, "statement_pages": len(statements)}


# Canonical KPI name → (table-reader item, statement kind)
_READER_KPIS = {
    "Total Revenue": ("total income", "profit_loss"),
    "Revenue from Operations": ("revenue from operations", "profit_loss"),
    "Other Income": ("other income", "profit_loss"),
    "Finance Costs": ("finance costs", "profit_loss"),
    "Depreciation & Amortization": ("depreciation", "profit_loss"),
    "Profit Before Tax (PBT)": ("profit before tax", "profit_loss"),
    "Profit After Tax (PAT) / Net Profit": ("profit for the year", "profit_loss"),
    "Earnings Per Share (EPS)": ("basic eps", "profit_loss"),
    "Total Assets": ("total assets", "balance_sheet"),
    "Total Equity / Shareholders Equity": ("total equity", "balance_sheet"),
    "Current Assets": ("total current assets", "balance_sheet"),
    "Current Liabilities": ("total current liabilities", "balance_sheet"),
    "Cash and Cash Equivalents": ("cash and cash equivalents", "balance_sheet"),
    "Operating Cash Flow": ("net cash from operating activities", "cash_flow"),
}
READER_SOURCE_PREFIX = "Table reader:"


def apply_table_reader(filing: Filing, db: Session) -> int:
    """
    Read headline KPIs straight from the financial statements with the deterministic table reader
    (consolidated preferred) and use them as the raw extracted values. Overrides the regex extractor
    whose wrong-row reads caused errors such as Airtel EPS 4.80 (statement: 45.96). Returns rows set.
    """
    from app.ml.table_reader import read_item

    if not filing.file_path:
        return 0
    existing = {k.name: k for k in db.query(KPI).filter(KPI.filing_id == filing.id).all()}
    n = 0
    for name, (item, kind) in _READER_KPIS.items():
        try:
            res = read_item(item, filing.id, filing.file_path, filing.fiscal_year, want_kind=kind)
        except Exception as e:  # a parsing problem must never break the pipeline
            logger.warning(f"Table reader failed for {name}: {e}")
            continue
        if not res.confident:
            continue
        k = existing.get(name)
        if k is None:
            from app.engines.kpi_extractor import KPI_CATEGORY
            k = KPI(filing_id=filing.id, name=name, currency=filing.currency, category=KPI_CATEGORY.get(name))
            db.add(k)
        k.raw_value = res.value
        k.unit = "crores"                    # raw marker: cleaning below normalises from raw_value
        k.page_number = res.page
        k.source_text = f"{READER_SOURCE_PREFIX} {res.label} ({res.scope}, p.{res.page})"
        k.is_verified = True
        k.verification_note = f"Read from the {res.scope} statement, page {res.page}"
        n += 1
    db.flush()
    return n


def clean_filing_kpis(filing: Filing, page_texts: List[str], db: Session) -> Dict:
    """Clean the KPIs of one filing in place. Returns a short summary."""
    n_reader = apply_table_reader(filing, db)
    # Derived ratios are recreated below; drop earlier ones so re-runs don't duplicate
    db.query(KPI).filter(KPI.filing_id == filing.id, KPI.source_text == DERIVED_SOURCE).delete()
    kpis: List[KPI] = db.query(KPI).filter(KPI.filing_id == filing.id).all()
    if not kpis:
        return {"cleaned": 0}

    # Idempotency: work from the raw values, never re-scale an already-clean value
    for k in kpis:
        if k.raw_value is None and k.unit not in CLEAN_UNITS:
            k.raw_value = k.value

    detected = detect_unit(page_texts)
    company: Company = db.query(Company).filter(Company.id == filing.company_id).first()

    rows = [{
        "kpi_id": k.id, "name": k.name, "value": k.raw_value, "report_id": filing.id,
        "company": company.name if company else filing.company_id, "sector": company.sector if company else None,
        "fiscal_year": filing.fiscal_year, "is_verified": int(bool(k.is_verified)), "category": k.category,
    } for k in kpis if not k.name.startswith("_")]

    # Already-cleaned KPIs of the company's other reports enable the stale-copy rule
    others = (
        db.query(KPI, Filing)
        .join(Filing, Filing.id == KPI.filing_id)
        .filter(Filing.company_id == filing.company_id, Filing.id != filing.id, KPI.unit.in_(CLEAN_UNITS))
        .all()
    )
    rows += [{
        "kpi_id": None, "name": k.name, "value": k.value, "report_id": f.id,
        "company": company.name if company else f.company_id, "sector": company.sector if company else None,
        "fiscal_year": f.fiscal_year, "is_verified": int(bool(k.is_verified)), "category": k.category,
    } for k, f in others]

    # Prior reports are already in ₹ crore → factor 1 for them
    report_units = {filing.id: detected["unit"]}
    report_units.update({f.id: "crore" for _, f in others})
    clean, log = clean_kpis(pd.DataFrame(rows), report_units)

    mine = log[(log["fiscal_year"] == filing.fiscal_year) & (log["company"] == (company.name if company else filing.company_id))] \
        if not log.empty else log
    reasons: Dict[str, List[str]] = {}
    for r in mine.itertuples():
        if r.rule != "scale":
            reasons.setdefault(r.kpi, []).append(f"[{r.rule}] {r.reason}")

    by_id = {k.id: k for k in kpis}
    n_rejected = 0
    for r in clean[clean["report_id"] == filing.id].itertuples():
        value = None if pd.isna(r.value) else float(r.value)
        notes = reasons.get(r.name, [])
        if isinstance(r.kpi_id, str) and r.kpi_id in by_id:
            k = by_id[r.kpi_id]
            k.value = value
            k.unit = r.unit
            k.source_unit = detected["unit"]
            if value is None:
                k.is_verified = False
                n_rejected += 1
            # Drop rule notes from a previous run ("[rule] …" segments), keep the extractor's own note
            base = [s for s in (k.verification_note or "").split(" | ") if s and not s.startswith("[")]
            if value is None:
                base = []  # the extractor's "passed sanity checks" no longer applies
            k.verification_note = " | ".join(["; ".join(notes)] * bool(notes) + base) or None
        elif value is not None:  # derived ratio
            db.add(KPI(
                filing_id=filing.id, name=r.name, value=value, unit=kpi_unit(r.name), currency=filing.currency,
                page_number=None, source_text=DERIVED_SOURCE, is_verified=True,
                verification_note="; ".join(notes) or "Derived", category=r.category or "Ratios",
                raw_value=None, source_unit=detected["unit"],
            ))

    filing.unit_scale = _UNIT_TO_FILING_SCALE.get(detected["unit"], filing.unit_scale)
    db.commit()

    summary = {
        "unit": detected["unit"], "evidence_from": detected["evidence_from"], "kpis": len(kpis), "from_table_reader": n_reader,
        "rejected": n_rejected, "rules": mine["rule"].value_counts().to_dict() if not mine.empty else {},
    }
    logger.info(f"KPI cleaning {filing.file_name}: {summary}")
    return summary
