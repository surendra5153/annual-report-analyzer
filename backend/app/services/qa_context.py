"""
Context the Q&A engine gets besides retrieved passages:

* filing_labels — "Company · FY2026 · amounts in ₹ lakh" per filing, so the model
  knows which report, year and unit every source comes from.
* kpi_facts     — the cleaned, verified KPI table of each filing (plus the
  company's prior-year values when that report is also loaded), offered to the
  model as an extra citable source. Retrieval often surfaces narrative pages for
  "what was the revenue" questions; the KPI table puts the statement figure in
  front of the model regardless.
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from app.db.models import Company, Filing, KPI

_UNIT_WORD = {"crores": "crore", "lakhs": "lakh", "millions": "million", "billions": "billion", "thousands": "thousand"}
_TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "billion": 100.0, "thousand": 1e-4}


def _inr(v: float, digits: int = 2) -> str:
    """Indian digit grouping: 1234567.8 → 12,34,567.80"""
    neg, v = v < 0, abs(v)
    whole, frac = f"{v:.{digits}f}".split(".") if digits else (f"{v:.0f}", "")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    s = ",".join(groups + [tail]) if groups else tail
    return ("-" if neg else "") + s + (f".{frac}" if frac else "")


def filing_labels(db: Session, filing_ids: List[str]) -> Dict[str, str]:
    labels = {}
    for f in db.query(Filing).filter(Filing.id.in_(filing_ids)).all():
        company = db.query(Company).filter(Company.id == f.company_id).first()
        unit = _UNIT_WORD.get((f.unit_scale or "").lower(), f.unit_scale or "crore")
        symbol = "₹" if (f.currency or "INR") == "INR" else f.currency
        labels[f.id] = f"{company.name if company else f.file_name} · FY{f.fiscal_year} · amounts in {symbol} {unit}"
    return labels


def _rupees(v: float) -> str:
    return ("-" if v < 0 else "") + "₹" + _inr(abs(v))


def _fmt(k: KPI) -> str:
    if k.unit == "x":
        return f"{k.value:.2f}×"
    if k.unit == "%":
        return f"{k.value:.2f}%"
    if k.unit == "₹/share":
        return f"{_rupees(round(k.value, 2))} per share"
    # Lead with the value as printed in the report (same unit as its statement pages), crore second
    if k.source_unit and k.source_unit != "crore" and k.raw_value is not None:
        return f"{_rupees(k.raw_value)} {k.source_unit} (= {_rupees(k.value)} crore)"
    return f"{_rupees(k.value)} crore"


def kpi_facts(db: Session, filing_ids: List[str], verified_only: bool = False) -> List[Dict]:
    """
    One citable pseudo-source per filing: {filing_id, page_number, text}.

    verified_only=False (default, chosen in notebook 05) includes every KPI that
    survived cleansing; ones the extractor could not cross-check are marked
    "(not cross-checked)". verified_only=True was configuration C, which withheld
    correct-but-unchecked rows such as Total Assets.
    """
    facts = []
    for f in db.query(Filing).filter(Filing.id.in_(filing_ids)).all():
        kpis = [k for k in db.query(KPI).filter(KPI.filing_id == f.id).all()
                if k.value is not None and (k.is_verified or not verified_only)]
        if not kpis:
            continue
        prior = (db.query(Filing)
                 .filter(Filing.company_id == f.company_id, Filing.fiscal_year == f.fiscal_year - 1)
                 .first())
        prior_kpis = {}
        if prior:
            prior_kpis = {k.name: k for k in db.query(KPI).filter(KPI.filing_id == prior.id).all()
                          if k.value is not None and (k.is_verified or not verified_only) and k.unit}
        company = db.query(Company).filter(Company.id == f.company_id).first()

        lines = []
        for k in sorted(kpis, key=lambda k: (k.category or "", k.name)):
            line = f"- {k.name}, FY{f.fiscal_year}: {_fmt(k)}"
            p = prior_kpis.get(k.name)
            if p is not None and p.unit == k.unit:
                line += f"; FY{prior.fiscal_year}: {_fmt(p)}"
                if k.unit == "₹ crore" and p.value:
                    line += f" (change {100 * (k.value - p.value) / abs(p.value):+.1f}%)"
            if not k.is_verified:
                line += " (not cross-checked)"
            if k.page_number:
                line += f" [page {k.page_number}]"
            lines.append(line)

        name = company.name if company else f.file_name
        header = (f"Extracted KPI table for {name}, annual report FY{f.fiscal_year}. Figures were extracted "
                  f"automatically and checked against accounting identities, but may still contain extraction errors "
                  f"and do not say whether a figure is standalone or consolidated; a full statement page takes "
                  f"precedence. Use the row whose name matches the question exactly (e.g. 'Total Assets' is not "
                  f"'Current Assets').")
        anchor = next((k.page_number for k in kpis if k.name == "Total Revenue" and k.page_number),
                      next((k.page_number for k in kpis if k.page_number), 0))
        facts.append({"filing_id": f.id, "page_number": anchor or 0, "text": header + "\n" + "\n".join(lines)})
    return facts
