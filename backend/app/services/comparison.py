"""
Cross-year and cross-company comparison service.
Normalizes units, currencies, and fiscal years before comparing.
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from loguru import logger

from app.db.models import Filing, KPI, Company


# Unit scale to absolute multiplier (relative to units)
UNIT_MULTIPLIERS = {
    "crores": 1_00_00_000,
    "lakhs": 1_00_000,
    "millions": 1_000_000,
    "billions": 1_000_000_000,
    "thousands": 1_000,
    "absolute": 1,
}

CURRENCY_TO_USD = {
    "INR": 0.012,
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
}


@dataclass
class NormalizedKPI:
    company_id: str
    company_name: str
    fiscal_year: int
    kpi_name: str
    raw_value: float
    normalized_value: float   # in USD absolute
    currency: str
    unit_scale: str


@dataclass
class ComparisonResult:
    kpi_name: str
    data_points: List[NormalizedKPI]
    chart_data: List[Dict]   # [{label, value, company, year}]


def _normalize_value(value: float, unit_scale: str, currency: str) -> float:
    multiplier = UNIT_MULTIPLIERS.get(unit_scale.lower(), 1)
    fx = CURRENCY_TO_USD.get(currency.upper(), 1.0)
    return value * multiplier * fx


def compare_filings(
    filing_ids: List[str],
    kpi_names: Optional[List[str]],
    db: Session,
) -> List[ComparisonResult]:
    """
    Compare KPIs across multiple filings (cross-year or cross-company).
    Values are normalized to USD absolute for fair comparison.
    """
    if not filing_ids:
        return []

    filings = db.query(Filing).filter(Filing.id.in_(filing_ids)).all()
    filing_map = {f.id: f for f in filings}
    company_ids = list({f.company_id for f in filings})
    companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
    company_map = {c.id: c for c in companies}

    # Gather all KPIs for these filings
    kpi_query = db.query(KPI).filter(KPI.filing_id.in_(filing_ids))
    if kpi_names:
        kpi_query = kpi_query.filter(KPI.name.in_(kpi_names))
    all_kpis = kpi_query.all()

    # Group by KPI name
    kpi_groups: Dict[str, List[NormalizedKPI]] = {}
    for kpi in all_kpis:
        if kpi.value is None:
            continue
        filing = filing_map.get(kpi.filing_id)
        if not filing:
            continue
        company = company_map.get(filing.company_id)
        if not company:
            continue

        # Cleaned KPIs carry their own unit: money is ₹ crore; ratios / % / per-share
        # values are scale-free and must not be multiplied by a unit factor.
        if kpi.unit in ("x", "%", "₹/share"):
            norm_val, unit_scale = kpi.value, kpi.unit
        else:
            unit_scale = "crores" if kpi.unit == "₹ crore" else filing.unit_scale
            norm_val = _normalize_value(kpi.value, unit_scale, filing.currency)
        point = NormalizedKPI(
            company_id=company.id,
            company_name=company.name,
            fiscal_year=filing.fiscal_year,
            kpi_name=kpi.name,
            raw_value=kpi.value,
            normalized_value=norm_val,
            currency=filing.currency,
            unit_scale=unit_scale,
        )
        kpi_groups.setdefault(kpi.name, []).append(point)

    results = []
    for kpi_name, points in kpi_groups.items():
        points.sort(key=lambda p: (p.company_name, p.fiscal_year))
        chart_data = [
            {
                "label": f"{p.company_name} {p.fiscal_year}",
                "company": p.company_name,
                "year": p.fiscal_year,
                "value": round(p.normalized_value, 2),
                "raw_value": round(p.raw_value, 2),
                "currency": p.currency,
                "unit_scale": p.unit_scale,
            }
            for p in points
        ]
        results.append(ComparisonResult(
            kpi_name=kpi_name,
            data_points=points,
            chart_data=chart_data,
        ))

    logger.info(f"Comparison produced {len(results)} KPI series for {len(filing_ids)} filings")
    return results
