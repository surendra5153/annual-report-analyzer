from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.api.schemas import ComparisonRequest, ComparisonResultOut, ComparisonChartPoint
from app.services.comparison import compare_filings

router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.post("/", response_model=List[ComparisonResultOut])
def compare(payload: ComparisonRequest, db: Session = Depends(get_db)):
    if len(payload.filing_ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 filing IDs to compare")
    

    results = compare_filings(
        filing_ids=payload.filing_ids,
        kpi_names=payload.kpi_names,
        db=db,
    )

    return [
        ComparisonResultOut(
            kpi_name=r.kpi_name,
            chart_data=[
                ComparisonChartPoint(**point) for point in r.chart_data
            ],
        )
        for r in results
    ]
