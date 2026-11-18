"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────

class ProcessingStatusEnum(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class RiskCategoryEnum(str, Enum):
    financial = "financial"
    regulatory = "regulatory"
    cybersecurity = "cybersecurity"
    climate = "climate"
    supply_chain = "supply_chain"
    operational = "operational"
    other = "other"


class SeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ── Company ────────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    ticker: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    is_tracked: bool = False


class CompanyOut(BaseModel):
    id: str
    name: str
    ticker: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    description: Optional[str]
    is_tracked: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Filing ─────────────────────────────────────────────────────────────────

class FilingOut(BaseModel):
    id: str
    company_id: str
    fiscal_year: int
    file_name: str
    status: ProcessingStatusEnum
    page_count: Optional[int]
    currency: str
    unit_scale: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── KPI ────────────────────────────────────────────────────────────────────

class KPIOut(BaseModel):
    id: str
    name: str
    value: Optional[float]
    unit: Optional[str]
    currency: Optional[str]
    page_number: Optional[int]
    source_text: Optional[str]
    is_verified: bool
    verification_note: Optional[str]
    category: Optional[str]
    raw_value: Optional[float] = None
    source_unit: Optional[str] = None

    class Config:
        from_attributes = True


# ── Risk ───────────────────────────────────────────────────────────────────

class RiskOut(BaseModel):
    id: str
    category: RiskCategoryEnum
    title: str
    description: str
    severity: SeverityEnum
    page_number: Optional[int]
    source_text: Optional[str]

    class Config:
        from_attributes = True


# ── Footnote Flag ──────────────────────────────────────────────────────────

class FootnoteFlagOut(BaseModel):
    id: str
    flag_type: str
    title: str
    description: str
    severity: SeverityEnum
    footnote_text: Optional[str]
    narrative_text: Optional[str]
    prior_year_text: Optional[str]
    page_number: Optional[int]
    ranking_score: float

    class Config:
        from_attributes = True


# ── Section Summary ────────────────────────────────────────────────────────

class SectionOut(BaseModel):
    id: str
    section_name: str
    summary: Optional[str]
    start_page: Optional[int]
    end_page: Optional[int]

    class Config:
        from_attributes = True


# ── Q&A ────────────────────────────────────────────────────────────────────

class QARequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    filing_ids: List[str] = Field(..., min_length=1)


class CitationOut(BaseModel):
    page_number: int
    excerpt: str
    filing_id: str


class QAResponse(BaseModel):
    question: str
    answer: str
    citations: List[CitationOut]
    confidence: str
    verified_against_kpi: bool
    kpi_verification_note: str


# ── Comparison ─────────────────────────────────────────────────────────────

class ComparisonRequest(BaseModel):
    filing_ids: List[str]
    kpi_names: Optional[List[str]] = None


class ComparisonChartPoint(BaseModel):
    label: str
    company: str
    year: int
    value: float
    raw_value: float
    currency: str
    unit_scale: str


class ComparisonResultOut(BaseModel):
    kpi_name: str
    chart_data: List[ComparisonChartPoint]


# ── Dashboard summary ──────────────────────────────────────────────────────

class DashboardOut(BaseModel):
    filing: FilingOut
    company: CompanyOut
    kpis: List[KPIOut]
    risks: List[RiskOut]
    top_flags: List[FootnoteFlagOut]
    sections: List[SectionOut]
    peer_suggestions: List[Dict[str, Any]]


# ── Job progress ──────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: str
    filing_id: str
    stage: str
    progress_pct: int
    status: str
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── PDF auto-detect ────────────────────────────────────────────────────────

class DetectResponse(BaseModel):
    """Result of scanning the first pages of a PDF for filing metadata."""
    is_financial_report: bool
    rejection_reason: Optional[str] = None   # set when is_financial_report=False

    # Detected fields (may be None if not found)
    company_name: Optional[str] = None
    ticker: Optional[str] = None
    fiscal_year: Optional[int] = None
    currency: Optional[str] = None           # e.g. "INR", "USD"
    unit_scale: Optional[str] = None         # e.g. "crores", "millions"
    report_type: Optional[str] = None        # e.g. "Annual Report", "10-K"
    confidence: str = "low"                  # "high" | "medium" | "low"
