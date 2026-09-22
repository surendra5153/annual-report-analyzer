from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Job
from app.api.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/by-filing/{filing_id}", response_model=JobOut)
def get_job_by_filing(filing_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.filing_id == filing_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="No job found for this filing")
    return job
