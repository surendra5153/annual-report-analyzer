from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.db.database import get_db
from app.db.models import Company, Filing, KPI, Risk, FootnoteFlag, ProcessingStatus
from app.api.schemas import CompanyCreate, CompanyOut
from app.engines.peer_discovery import find_peers

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=List[CompanyOut])
def list_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Company).offset(skip).limit(limit).all()


@router.post("/", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    existing = db.query(Company).filter(Company.ticker == payload.ticker).first()
    if existing:
        raise HTTPException(status_code=409, detail="Company with this ticker already exists")
    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(company_id: str, payload: CompanyCreate, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(company, k, v)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=204)
def delete_company(company_id: str, db: Session = Depends(get_db)):
    from app.db.models import Filing, Job as JobModel
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    # Delete Job rows first (FK: jobs.filing_id → filings.id)
    filing_ids = [f.id for f in db.query(Filing).filter(Filing.company_id == company_id).all()]
    if filing_ids:
        db.query(JobModel).filter(JobModel.filing_id.in_(filing_ids)).delete(synchronize_session=False)
        db.commit()
    db.delete(company)
    db.commit()


@router.get("/{company_id}/peers")
def get_peers(company_id: str, top_k: int = 5, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    all_companies = [
        {"id": c.id, "name": c.name, "ticker": c.ticker, "sector": c.sector, "description": c.description}
        for c in db.query(Company).all()
    ]
    peers = find_peers(
        target_description=company.description or company.name,
        all_companies=all_companies,
        target_company_id=company_id,
        top_k=top_k,
    )
    return [
        {
            "company_id": p.company_id,
            "company_name": p.company_name,
            "ticker": p.ticker,
            "sector": p.sector,
            "similarity_score": p.similarity_score,
            "reason": p.reason,
        }
        for p in peers
    ]


@router.get("/{company_id}/profile")
def get_company_profile(company_id: str, db: Session = Depends(get_db)):
    """
    Full company profile:
    - All filings with status
    - Multi-year KPI trends (per metric, sorted by fiscal year)
    - Risk count trend per year
    - Flag count trend per year
    - Peer suggestions
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    filings = (
        db.query(Filing)
        .filter(Filing.company_id == company_id)
        .order_by(Filing.fiscal_year.asc())
        .all()
    )

    completed = [f for f in filings if f.status == ProcessingStatus.COMPLETED]

    # ── KPI trend: {metric_name: [{year, value, currency, unit_scale}]} ───
    kpi_trend: Dict[str, List[Dict[str, Any]]] = {}
    for filing in completed:
        kpis = db.query(KPI).filter(KPI.filing_id == filing.id).all()
        for k in kpis:
            if k.value is None:
                continue
            if k.name not in kpi_trend:
                kpi_trend[k.name] = []
            kpi_trend[k.name].append({
                "fiscal_year": filing.fiscal_year,
                "value": k.value,
                "currency": k.currency or filing.currency,
                "unit_scale": k.unit or filing.unit_scale,
                "is_verified": k.is_verified,
            })

    # yearly_stats includes ALL filings (not just completed) so the profile
    # shows processing/pending filings too
    yearly_stats = []
    for filing in filings:
        risk_count = db.query(Risk).filter(Risk.filing_id == filing.id).count()
        flag_count = (
            db.query(FootnoteFlag)
            .filter(FootnoteFlag.filing_id == filing.id)
            .count()
        )
        kpi_count = db.query(KPI).filter(KPI.filing_id == filing.id).count()
        yearly_stats.append({
            "filing_id": filing.id,
            "fiscal_year": filing.fiscal_year,
            "kpi_count": kpi_count,
            "risk_count": risk_count,
            "flag_count": flag_count,
            "status": filing.status,
            "file_name": filing.file_name,
            "page_count": filing.page_count,
            "currency": filing.currency,
            "unit_scale": filing.unit_scale,
        })

    # ── Peers ──────────────────────────────────────────────────────────────
    all_cos = [
        {"id": c.id, "name": c.name, "ticker": c.ticker,
         "sector": c.sector, "description": c.description}
        for c in db.query(Company).all()
    ]
    peers = find_peers(
        target_description=company.description or company.name,
        all_companies=all_cos,
        target_company_id=company_id,
        top_k=5,
    )

    return {
        "company": {
            "id": company.id,
            "name": company.name,
            "ticker": company.ticker,
            "sector": company.sector,
            "industry": company.industry,
            "description": company.description,
            "is_tracked": company.is_tracked,
        },
        "filings": yearly_stats,
        "kpi_trends": kpi_trend,
        "peers": [
            {
                "company_id": p.company_id,
                "name": p.company_name,
                "ticker": p.ticker,
                "score": p.similarity_score,
            }
            for p in peers
        ],
    }
