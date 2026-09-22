from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from app.db.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class ProcessingStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


class RiskCategory(str, enum.Enum):
    FINANCIAL     = "financial"
    REGULATORY    = "regulatory"
    CYBERSECURITY = "cybersecurity"
    CLIMATE       = "climate"
    SUPPLY_CHAIN  = "supply_chain"
    OPERATIONAL   = "operational"
    OTHER         = "other"


class FlagSeverity(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------
class Company(Base):
    __tablename__ = "companies"

    id          = Column(String, primary_key=True, default=gen_uuid)
    name        = Column(String(255), nullable=False)
    ticker      = Column(String(20),  unique=True, nullable=True)
    sector      = Column(String(100), nullable=True)
    industry    = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    is_tracked  = Column(Boolean, default=False)
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, onupdate=func.now())

    filings = relationship("Filing", back_populates="company", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Job  (tracks async pipeline progress per filing)
# ---------------------------------------------------------------------------
class Job(Base):
    __tablename__ = "jobs"

    id           = Column(String, primary_key=True, default=gen_uuid)
    filing_id    = Column(String, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, unique=True)
    stage        = Column(String(50),  default="queued")   # queued/parsing/chunking/...
    progress_pct = Column(Integer, default=0)
    status       = Column(String(20),  default="queued")   # queued/running/done/failed
    error_message= Column(Text, nullable=True)
    updated_at   = Column(DateTime, server_default=func.now(), onupdate=func.now())

    filing = relationship("Filing")


# ---------------------------------------------------------------------------
# Filing
# ---------------------------------------------------------------------------
class Filing(Base):
    __tablename__ = "filings"

    id             = Column(String, primary_key=True, default=gen_uuid)
    company_id     = Column(String, ForeignKey("companies.id"), nullable=False)
    fiscal_year    = Column(Integer, nullable=False)
    file_path      = Column(String(500), nullable=False)
    file_name      = Column(String(255), nullable=False)
    file_size_bytes= Column(Integer, nullable=True)
    status         = Column(String(20), default=ProcessingStatus.PENDING)
    error_message  = Column(Text, nullable=True)
    page_count     = Column(Integer, nullable=True)
    currency       = Column(String(10), default="INR")
    unit_scale     = Column(String(20), default="crores")
    # Full document text stored so prior-year footnote engine avoids re-parsing the PDF
    full_text      = Column(Text, nullable=True)
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, onupdate=func.now())

    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", name="uq_company_year"),)

    company        = relationship("Company", back_populates="filings")
    kpis           = relationship("KPI",           back_populates="filing", cascade="all, delete-orphan")
    risks          = relationship("Risk",          back_populates="filing", cascade="all, delete-orphan")
    footnote_flags = relationship("FootnoteFlag",  back_populates="filing", cascade="all, delete-orphan")
    sections       = relationship("ReportSection", back_populates="filing", cascade="all, delete-orphan")

# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------
class KPI(Base):
    __tablename__ = "kpis"

    id                = Column(String, primary_key=True, default=gen_uuid)
    filing_id         = Column(String, ForeignKey("filings.id"), nullable=False)
    name              = Column(String(200), nullable=False)
    value             = Column(Float, nullable=True)
    unit              = Column(String(50),  nullable=True)
    currency          = Column(String(10),  nullable=True)
    page_number       = Column(Integer, nullable=True)
    source_text       = Column(Text, nullable=True)
    is_verified       = Column(Boolean, default=False)
    verification_note = Column(Text, nullable=True)
    category          = Column(String(100), nullable=True)
    created_at        = Column(DateTime, server_default=func.now())

    filing = relationship("Filing", back_populates="kpis")


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------
class Risk(Base):
    __tablename__ = "risks"

    id          = Column(String, primary_key=True, default=gen_uuid)
    filing_id   = Column(String, ForeignKey("filings.id"), nullable=False)
    category    = Column(String(50), nullable=False)
    title       = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    severity    = Column(String(20), default=FlagSeverity.MEDIUM)
    page_number = Column(Integer, nullable=True)
    source_text = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    filing = relationship("Filing", back_populates="risks")


# ---------------------------------------------------------------------------
# Footnote / consistency flag
# ---------------------------------------------------------------------------
class FootnoteFlag(Base):
    __tablename__ = "footnote_flags"

    id             = Column(String, primary_key=True, default=gen_uuid)
    filing_id      = Column(String, ForeignKey("filings.id"), nullable=False)
    flag_type      = Column(String(100), nullable=False)
    title          = Column(String(300), nullable=False)
    description    = Column(Text, nullable=False)
    severity       = Column(String(20), default=FlagSeverity.MEDIUM)
    footnote_text  = Column(Text, nullable=True)
    narrative_text = Column(Text, nullable=True)
    prior_year_text= Column(Text, nullable=True)
    page_number    = Column(Integer, nullable=True)
    ranking_score  = Column(Float, default=0.0)
    created_at     = Column(DateTime, server_default=func.now())

    filing = relationship("Filing", back_populates="footnote_flags")


# ---------------------------------------------------------------------------
# Report section
# ---------------------------------------------------------------------------
class ReportSection(Base):
    __tablename__ = "report_sections"

    id           = Column(String, primary_key=True, default=gen_uuid)
    filing_id    = Column(String, ForeignKey("filings.id"), nullable=False)
    section_name = Column(String(200), nullable=False)
    summary      = Column(Text, nullable=True)
    raw_text     = Column(Text, nullable=True)
    start_page   = Column(Integer, nullable=True)
    end_page     = Column(Integer, nullable=True)
    created_at   = Column(DateTime, server_default=func.now())

    filing = relationship("Filing", back_populates="sections")
