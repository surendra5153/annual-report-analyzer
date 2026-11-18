# Annual Report Analyzer - Technical Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [How It Works](#how-it-works)
4. [Technology Stack](#technology-stack)
5. [Core Components](#core-components)
6. [Data Flow](#data-flow)
7. [Database Schema](#database-schema)
8. [API Endpoints](#api-endpoints)
9. [Machine Learning Pipeline](#machine-learning-pipeline)
10. [Deployment](#deployment)

---

## Project Overview

The **Annual Report Analyzer** (NLP-07) is an AI-powered system designed to process, analyze, and extract insights from corporate annual reports and financial filings. It leverages Large Language Models (LLMs), natural language processing, and machine learning to provide:

- **Automated KPI Extraction**: Extracts 28 canonical financial KPIs from unstructured PDF reports
- **Risk Classification**: Identifies and categorizes risks (financial, regulatory, cyber, climate, supply chain)
- **Anomaly Detection**: Detects year-over-year trends and inconsistencies
- **RAG-based Q&A**: Natural language question-answering with source citations
- **Financial Comparison**: Side-by-side comparison of up to 3 companies
- **Peer Discovery**: Finds similar companies using embedding similarity
- **Interactive Dashboard**: Real-time metrics, risk feeds, and processing status

### Use Cases
- Financial analysts reviewing multiple annual reports
- Compliance teams checking regulatory disclosures
- Investment firms performing due diligence
- Corporate governance monitoring
- Automated competitive analysis

---

## System Architecture

The system follows a **three-tier architecture** with a modern microservices approach:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
│  React 18 + Vite + TailwindCSS + React Query + React Router    │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST API (HTTP/JSON)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Backend Layer (FastAPI)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ API Routes   │  │  Services    │  │   Engines    │        │
│  │ - Companies  │  │ - Pipeline   │  │ - Ingestion  │        │
│  │ - Filings    │  │ - Comparison │  │ - KPI Extract│        │
│  │ - Q&A        │  │ - QA Context │  │ - Risk       │        │
│  │ - ML         │  │ - KPI Clean  │  │ - Summarizer │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   SQLite/    │  │   ChromaDB   │  │ Redis + File │
│  PostgreSQL  │  │  (Vectors)   │  │   Storage    │
│  (Metadata)  │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Architecture Components

#### 1. **Frontend Layer**
- **Framework**: React 18 with functional components and hooks
- **Routing**: React Router v6 for SPA navigation
- **State Management**: TanStack React Query for server state, React hooks for local state
- **UI Components**: Radix UI primitives with custom styling
- **Styling**: TailwindCSS with custom design tokens
- **Charts**: Recharts for financial visualizations
- **Build Tool**: Vite for fast development and optimized production builds

#### 2. **Backend Layer (FastAPI)**
- **API Framework**: FastAPI for high-performance async REST API
- **ORM**: SQLAlchemy 2.0 with async support
- **Validation**: Pydantic v2 for request/response schemas
- **CORS**: Configured for local development and production
- **Logging**: Loguru for structured logging
- **Task Queue**: Celery with Redis (optional for distributed processing)

#### 3. **Data Layer**
- **Relational DB**: SQLite (dev) / PostgreSQL (prod) for structured data
- **Vector Store**: ChromaDB for document embeddings and similarity search
- **File Storage**: Local filesystem for uploaded PDFs
- **Cache**: Redis for Celery task results (optional)

#### 4. **ML/AI Layer**
- **LLM**: OpenAI-compatible API (Ollama for local, OpenAI/Gemini for cloud)
- **Embeddings**: BAAI/bge-small-en-v1.5 (run locally on CPU/GPU)
- **Reranker**: cross-encoder/ms-marco-MiniLM-L-6-v2
- **PDF Processing**: PyMuPDF + pdfplumber for text/table extraction
- **BM25**: Sparse retrieval for keyword matching

---

## How It Works

### End-to-End Processing Flow

```
1. Upload PDF → 2. Ingestion → 3. Chunking → 4. Embedding → 5. Analysis → 6. Storage
```

### Detailed Processing Pipeline

#### **Step 1: PDF Upload**
User uploads an annual report PDF through the web interface. The file is validated (size, format) and saved to the uploads directory.

#### **Step 2: Document Ingestion**
The `ingestion.py` engine processes the PDF:
- **Text Extraction**: PyMuPDF extracts raw text from each page
- **Table Detection**: pdfplumber identifies and extracts tabular data
- **Image Extraction**: (Optional) Vision models describe charts/graphs
- **Output**: `IngestedDocument` with pages, tables, and metadata

#### **Step 3: Chunking**
The `chunking.py` engine splits the document into manageable pieces:
- **Text Chunks**: Sliding window with overlap (400 tokens for Q&A, 1000 for extraction)
- **Table Chunks**: Each table becomes a separate chunk with metadata
- **Page Tracking**: Each chunk maintains page number references
- **Output**: List of `Chunk` objects with text, metadata, and embeddings

#### **Step 4: Embedding & Indexing**
The `embedding.py` engine creates vector representations:
- **Model**: BAAI/bge-small-en-v1.5 (384-dimensional embeddings)
- **Batch Processing**: Efficient batching for GPU/CPU
- **Deduplication**: Removes near-duplicate chunks
- **Storage**: Vectors stored in ChromaDB collection
- **Indexing**: HNSW index for fast similarity search

#### **Step 5: Parallel Analysis**
Multiple analysis engines run concurrently:

**A. KPI Extraction** (`kpi_extractor.py`)
- Pattern matching on table cells and text lines
- Extracts 28 canonical KPIs (revenue, profit, assets, etc.)
- Supports Indian accounting standards (INDAS)
- Unit normalization (lakhs → crores, millions → crores)
- Stores in `kpis` table with source citations

**B. Risk Classification** (`risk_classifier.py`)
- Keyword pre-scanning for risk sections
- LLM-based classification into 7 categories
- Severity scoring (low/medium/high/critical)
- Stores in `risks` table

**C. Anomaly Detection** (`anomaly_detector.py`)
- Year-over-year percentage change analysis
- Z-score computation for multi-year trends
- Statistical outlier detection
- Generates `FootnoteFlag` records for significant deviations

**D. Document Summarization** (`summarizer.py`)
- Section detection (business overview, risks, financials)
- LLM-based summarization of each section
- Stores in `report_sections` table

**E. Footnote Analysis** (`footnote_engine.py`)
- Cross-references footnotes with narrative text
- Compares current year promises vs. prior year outcomes
- LLM-based consistency checking
- Flags discrepancies

#### **Step 6: Storage & Indexing**
All extracted data is stored in the database with proper relationships and indexed for fast retrieval.

### Q&A Pipeline (RAG)

When a user asks a question:

```
Question → Hybrid Retrieval → Reranking → Context Building → LLM Generation → Response
```

**1. Hybrid Retrieval** (`rag_qa.py` + `bm25.py` + `fusion.py`)
- **Dense Retrieval**: ChromaDB similarity search (semantic matching)
- **Sparse Retrieval**: BM25 keyword search
- **Fusion**: Reciprocal Rank Fusion (RRF) combines both rankings
- **Candidates**: Top 30 chunks from each retriever

**2. Reranking** (`reranker.py`)
- Cross-encoder model re-scores all candidates
- Precision-focused: boosts truly relevant chunks
- Returns top 10-15 most relevant chunks

**3. Context Building**
- Combines retrieved chunks into a context block
- Adds extracted KPI table (structured facts)
- For numeric questions: includes full financial statement pages
- Cites sources (page numbers, filing names)

**4. LLM Generation**
- Prompt: Question + Context + Instructions
- Model: qwen2.5:3b (local) or gpt-4o-mini (cloud)
- Temperature: 0.1 (factual responses)
- Returns answer with inline citations

**5. Deterministic Table Reader** (Optional)
- For simple numeric lookups ("What is revenue for 2023?")
- Directly reads from extracted KPI table
- Skips LLM call (faster, more accurate)

---

## Technology Stack

### Backend Technologies

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Framework** | FastAPI | 0.111.0 | Async REST API framework |
| **Runtime** | Python | 3.11+ | Backend language |
| **Server** | Uvicorn | 0.29.0 | ASGI server |
| **ORM** | SQLAlchemy | 2.0.30 | Database ORM |
| **Migrations** | Alembic | 1.13.1 | Database migrations |
| **Validation** | Pydantic | 2.7.1 | Data validation |
| **Database** | SQLite/PostgreSQL | - | Relational storage |
| **Vector DB** | ChromaDB | 0.5.0 | Embedding storage |
| **Task Queue** | Celery | 5.4.0 | Async job processing |
| **Cache** | Redis | 5.0.4 | Celery broker |

### ML/AI Technologies

| Category | Technology | Purpose |
|----------|-----------|---------|
| **LLM Client** | OpenAI SDK | 1.30.1 | LLM API calls |
| **Local LLM** | Ollama | Latest | Local model runtime |
| **Embeddings** | sentence-transformers | 3.0.1 | Text → vectors |
| **Embedding Model** | BAAI/bge-small-en-v1.5 | 384-dim embeddings |
| **Reranker** | cross-encoder/ms-marco-MiniLM-L-6-v2 | Cross-encoder reranking |
| **PDF Parsing** | PyMuPDF | 1.24.3 | Text extraction |
| **Table Extraction** | pdfplumber | 0.11.0 | Table detection |
| **Numeric Processing** | NumPy | 1.26.4 | Array operations |
| **Data Processing** | Pandas | 2.2.2 | DataFrame operations |

### Frontend Technologies

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Framework** | React | 18.3.1 | UI library |
| **Build Tool** | Vite | 5.3.1 | Dev server + bundler |
| **Routing** | React Router | 6.23.1 | Client-side routing |
| **State** | TanStack Query | 5.45.1 | Server state management |
| **HTTP Client** | Axios | 1.7.2 | API requests |
| **Styling** | TailwindCSS | 3.4.4 | Utility-first CSS |
| **UI Components** | Radix UI | Latest | Accessible primitives |
| **Charts** | Recharts | 2.12.7 | Data visualization |
| **Icons** | Lucide React | 0.395.0 | Icon library |
| **Animation** | Framer Motion | 14.0.0 | Animations |
| **Markdown** | react-markdown | 10.1.0 | Markdown rendering |
| **PDF Viewer** | react-pdf | 9.2.1 | PDF viewing |
| **Notifications** | Sonner | 2.0.8 | Toast notifications |

### DevOps & Infrastructure

| Tool | Purpose |
|------|---------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |
| **Git** | Version control |
| **pytest** | Testing framework |
| **Loguru** | Structured logging |
| **python-dotenv** | Environment variables |

---

## Core Components

### Backend Modules

#### **1. API Layer** (`app/api/`)

**Routes:**
- `companies.py`: Company CRUD operations
- `filings.py`: Filing upload, status, deletion
- `qa.py`: Question-answering endpoint
- `comparison.py`: Multi-company comparison
- `ml.py`: ML model status, peer discovery
- `jobs.py`: Processing job status

**Schemas:**
- Pydantic models for request/response validation
- Type-safe API contracts

#### **2. Core Layer** (`app/core/`)

- **`config.py`**: Settings management (Pydantic BaseSettings)
  - LLM configuration
  - Database URLs
  - Chunking parameters
  - Model paths
  
- **`llm_client.py`**: Unified LLM interface
  - OpenAI-compatible API wrapper
  - Retry logic with exponential backoff
  - Token counting
  - Timeout handling

#### **3. Database Layer** (`app/db/`)

- **`database.py`**: SQLAlchemy setup
  - Engine creation
  - Session management
  - Auto-column sync
  
- **`models.py`**: ORM models
  - `Company`: Company metadata
  - `Filing`: Annual report records
  - `KPI`: Extracted metrics
  - `Risk`: Classified risks
  - `FootnoteFlag`: Anomalies/flags
  - `ReportSection`: Document sections
  - `Job`: Processing status

#### **4. Engines Layer** (`app/engines/`)

Core processing engines:

- **`ingestion.py`**: PDF → structured data
- **`chunking.py`**: Document → chunks
- **`embedding.py`**: Text → vectors
- **`kpi_extractor.py`**: Tables → KPIs
- **`risk_classifier.py`**: Text → risk categories
- **`anomaly_detector.py`**: KPIs → anomaly flags
- **`summarizer.py`**: Sections → summaries
- **`footnote_engine.py`**: Footnotes → consistency flags
- **`rag_qa.py`**: Question → answer pipeline
- **`peer_discovery.py`**: Company → similar companies

#### **5. ML Layer** (`app/ml/`)

Machine learning utilities:

- **`bm25.py`**: Sparse retrieval (keyword search)
- **`fusion.py`**: Reciprocal Rank Fusion
- **`reranker.py`**: Cross-encoder reranking
- **`kpi_clean.py`**: KPI value normalization
- **`label_pages.py`**: Page type classification
- **`page_classifier.py`**: ML page classifier
- **`statement_index.py`**: Financial statement indexing
- **`table_reader.py`**: Deterministic table lookups
- **`text_clean.py`**: Text preprocessing

#### **6. Services Layer** (`app/services/`)

Business logic orchestration:

- **`pipeline.py`**: End-to-end processing orchestration
- **`comparison.py`**: Multi-company comparison logic
- **`kpi_cleaning.py`**: KPI normalization service
- **`qa_context.py`**: Q&A context building

#### **7. Workers Layer** (`app/workers/`)

Async task processing (optional):

- **`celery_app.py`**: Celery configuration
- **`tasks.py`**: Async task definitions
- **`filing_watcher.py`**: Automated filing discovery

### Frontend Structure

```
frontend/src/
├── pages/              # Route components
│   ├── Home.jsx
│   ├── Companies.jsx
│   ├── Filings.jsx
│   ├── QA.jsx
│   └── Comparison.jsx
├── components/         # Reusable UI components
│   ├── ui/            # Base components (Button, Card, etc.)
│   ├── CompanyCard.jsx
│   ├── FilingCard.jsx
│   └── RiskFeed.jsx
├── services/          # API client
│   └── api.js
├── lib/               # Utilities
│   └── utils.js
└── data/              # Static data/constants
```

---

## Data Flow

### Document Processing Flow

```
User Upload
    │
    ▼
┌─────────────────────┐
│  FastAPI Endpoint   │ ← POST /api/filings/{company_id}/upload
│  (filings.py)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Create Job Record  │ ← Job status tracking
│  (status: queued)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Pipeline Service    │
│ (pipeline.py)       │
└──────────┬──────────┘
           │
           ├─► Ingestion Engine ──► IngestedDocument
           │
           ├─► Chunking Engine ──► Chunks
           │
           ├─► Embedding Engine ──► Vectors → ChromaDB
           │
           ├─► KPI Extractor ──► KPIs → Database
           │
           ├─► Risk Classifier ──► Risks → Database
           │
           ├─► Anomaly Detector ──► Flags → Database
           │
           └─► Summarizer ──► Sections → Database
           
           ▼
┌─────────────────────┐
│  Update Job Status  │ ← status: completed
│  Filing Status      │ ← status: completed
└─────────────────────┘
```

### Q&A Request Flow

```
User Question
    │
    ▼
┌─────────────────────────────┐
│  POST /api/qa               │
│  Body: { question, filings }│
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  RAG Q&A Engine             │
│  (rag_qa.py)                │
└──────────┬──────────────────┘
           │
           ├─► Question Embedding
           │   (bge-small-en-v1.5)
           │
           ├─► Dense Retrieval (ChromaDB)
           │   Top 30 by cosine similarity
           │
           ├─► Sparse Retrieval (BM25)
           │   Top 30 by keyword match
           │
           ├─► Reciprocal Rank Fusion
           │   Merge rankings
           │
           ├─► Cross-Encoder Reranking
           │   Top 15 final candidates
           │
           ├─► Context Building
           │   • Retrieved chunks
           │   • KPI table
           │   • Statement pages (numeric Q)
           │
           ├─► LLM Generation
           │   • Model: qwen2.5:3b / gpt-4o-mini
           │   • Prompt: Q + Context
           │   • Temperature: 0.1
           │
           └─► Response with Citations
                 │
                 ▼
┌─────────────────────────────┐
│  { answer, citations }      │
│  Return to client           │
└─────────────────────────────┘
```

---

## Database Schema

### Entity Relationship Diagram

```
┌──────────────┐         ┌──────────────┐
│   Company    │1      *│    Filing    │
│──────────────│◄────────│──────────────│
│ id (PK)      │         │ id (PK)      │
│ name         │         │ company_id   │
│ ticker       │         │ fiscal_year  │
│ sector       │         │ file_path    │
│ industry     │         │ status       │
│ description  │         │ page_count   │
│ is_tracked   │         │ currency     │
└──────────────┘         │ unit_scale   │
                         │ full_text    │
                         └───────┬──────┘
                                 │
                   ┌─────────────┼─────────────┬─────────────┐
                   │             │             │             │
                   ▼             ▼             ▼             ▼
           ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
           │     KPI     │ │    Risk     │ │ FootnoteFlag│ │ReportSection │
           │─────────────│ │─────────────│ │─────────────│ │──────────────│
           │ id (PK)     │ │ id (PK)     │ │ id (PK)     │ │ id (PK)      │
           │ filing_id   │ │ filing_id   │ │ filing_id   │ │ filing_id    │
           │ name        │ │ category    │ │ flag_type   │ │ section_name │
           │ value       │ │ title       │ │ title       │ │ summary      │
           │ unit        │ │ description │ │ description │ │ raw_text     │
           │ currency    │ │ severity    │ │ severity    │ │ start_page   │
           │ page_number │ │ page_number │ │ footnote_... │ │ end_page     │
           │ source_text │ │ source_text │ │ page_number │ └──────────────┘
           │ raw_value   │ └─────────────┘ │ ranking_...  │
           │ source_unit │                 └─────────────┘
           └─────────────┘

           ┌──────────────┐
           │     Job      │ (1:1 with Filing)
           │──────────────│
           │ id (PK)      │
           │ filing_id    │
           │ stage        │
           │ progress_pct │
           │ status       │
           │ error_msg    │
           └──────────────┘
```

### Key Tables

**Companies**
- Stores company metadata
- `ticker` is unique identifier
- `is_tracked` marks companies for automated filing watch

**Filings**
- One filing per company per fiscal year
- `status`: pending → processing → completed/failed
- Stores full extracted text for cross-year analysis
- Unique constraint on (company_id, fiscal_year)

**KPIs**
- Extracted financial metrics
- `raw_value` + `source_unit` preserve original format
- `value` is normalized to report's base unit (e.g., crores)
- `category` groups related KPIs

**Risks**
- Classified into 7 categories (financial, regulatory, cyber, etc.)
- `severity`: low/medium/high/critical
- Includes page number and source text citations

**FootnoteFlags**
- Anomalies and inconsistencies
- `flag_type`: yoy_spike, yoy_drop, footnote_inconsistency, etc.
- `ranking_score` for prioritization

**ReportSections**
- Document structure (business overview, risks, financials)
- LLM-generated summaries
- Page ranges for each section

**Jobs**
- Tracks async processing progress
- `stage`: queued/parsing/chunking/embedding/extracting/...
- `progress_pct`: 0-100%
- Real-time updates for UI

### Vector Storage (ChromaDB)

**Collection**: `annual_reports_v2`

Each chunk stored with:
- `embedding`: 384-dim float vector
- `metadata`:
  - `filing_id`: Links to Filing table
  - `page_num`: Source page
  - `chunk_type`: text/table/image
  - `text`: Original text content

---

## API Endpoints

### Companies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/companies` | List all companies |
| POST | `/api/companies` | Create company |
| GET | `/api/companies/{id}` | Get company details |
| PUT | `/api/companies/{id}` | Update company |
| DELETE | `/api/companies/{id}` | Delete company |

### Filings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/companies/{id}/filings` | List filings for company |
| POST | `/api/filings/{company_id}/upload` | Upload annual report PDF |
| GET | `/api/filings/{id}` | Get filing details |
| GET | `/api/filings/{id}/kpis` | Get extracted KPIs |
| GET | `/api/filings/{id}/risks` | Get classified risks |
| GET | `/api/filings/{id}/sections` | Get document sections |
| DELETE | `/api/filings/{id}` | Delete filing |

### Q&A

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/qa` | Ask question about filings |

**Request Body:**
```json
{
  "question": "What was the revenue growth in 2023?",
  "filing_ids": ["filing-uuid-1", "filing-uuid-2"],
  "top_k": 15
}
```

**Response:**
```json
{
  "answer": "Revenue grew 15.2% to ₹5,432 crore...",
  "citations": [
    {"page": 42, "filing_name": "Company A FY2023"},
    {"page": 18, "filing_name": "Company A FY2022"}
  ],
  "confidence": 0.89
}
```

### Comparison

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/comparison` | Compare multiple companies |

**Request Body:**
```json
{
  "filing_ids": ["filing1", "filing2", "filing3"],
  "metrics": ["revenue", "net_profit", "total_assets"]
}
```

### ML

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ml/models/status` | Check model availability |
| POST | `/api/ml/peers` | Find similar companies |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs/{filing_id}` | Get processing status |

---

## Machine Learning Pipeline

### Models Used

#### 1. **Embedding Model: BAAI/bge-small-en-v1.5**
- **Type**: Dense retrieval model
- **Dimensions**: 384
- **Purpose**: Convert text chunks to semantic vectors
- **Training**: Pre-trained on 1B+ text pairs
- **Deployment**: Runs locally on CPU/GPU
- **Speed**: ~500 chunks/sec on GPU

#### 2. **Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2**
- **Type**: Cross-encoder (bi-encoder)
- **Purpose**: Precision reranking of retrieval candidates
- **Input**: (question, chunk) pairs
- **Output**: Relevance scores
- **Deployment**: Runs locally
- **Speed**: ~100 pairs/sec

#### 3. **LLM: qwen2.5:3b / gpt-4o-mini**
- **Local**: Qwen 2.5 (3B parameters) via Ollama
  - 8K context window
  - Quantized for fast inference
  - ~20 tokens/sec on RTX 3060
- **Cloud**: GPT-4o-mini via OpenAI API
  - 128K context window
  - Higher quality, slower, paid

#### 4. **BM25 (Sparse Retrieval)**
- Classic TF-IDF based keyword search
- No training required
- Built on-the-fly from document corpus
- Excellent for exact keyword matches

### Hybrid Retrieval Strategy

The system uses **Reciprocal Rank Fusion (RRF)** to combine:

1. **Dense Retrieval** (semantic similarity)
   - Query: "What were the major cybersecurity risks?"
   - Finds chunks about "data breaches", "IT security", "cyber threats"
   
2. **Sparse Retrieval** (keyword matching)
   - Query: "revenue FY2023"
   - Finds exact keyword matches

RRF Formula:
```
RRF_score(chunk) = Σ 1 / (k + rank_i)
where k=60, rank_i is position in retriever i
```

This ensures both semantic and keyword relevance.

### Page Classification

**Statement Index** (`statement_index.py`) classifies each page:
- `financial_statement`: Income statement, balance sheet, cash flow
- `narrative`: Management discussion, business overview
- `footnotes`: Accounting policies, disclosures
- `other`: Cover page, table of contents

**Purpose**: For numeric questions, directly include full financial statement pages (tables) rather than truncated chunks.

### KPI Normalization Pipeline

**Problem**: Annual reports use inconsistent units (lakhs, crores, millions, thousands)

**Solution** (`kpi_clean.py`):
1. Detect report's base unit from context clues
2. Parse raw value strings ("5,432.5 Cr", "₹ 54,325 lakh")
3. Convert all KPIs to report's base unit
4. Store both `raw_value` and normalized `value`

**Example**:
- Input: "Revenue: ₹ 54,325 lakh"
- Parsed: raw_value=54325, source_unit="lakh"
- Normalized: value=5432.5, unit="crore"

---

## Deployment

### Local Development

**Requirements:**
- Python 3.11+
- Node.js 18+
- Ollama (for local LLM)

**Setup:**
```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Docker Compose Deployment

**Architecture:**
```
services:
  - backend: FastAPI app
  - frontend: Nginx serving static React build
  - postgres: PostgreSQL database
  - redis: Task queue broker
  - celery: Background workers
  - chroma: Vector database (optional)
```

**Deploy:**
```bash
cp backend/.env.example backend/.env
# Edit .env with production values
docker compose up -d --build
```

### Cloud Deployment Options

#### **1. Railway**
- Auto-detects Dockerfile
- Built-in PostgreSQL
- Environment variable management
- Auto-deploy from GitHub
- Cost: ~$20-50/month

#### **2. Render**
- Web Service (backend) + Static Site (frontend)
- Managed PostgreSQL
- Zero-config deploys
- Free tier available
- Cost: Free - $50/month

#### **3. AWS**
- ECS Fargate: Container orchestration
- RDS PostgreSQL: Managed database
- S3: PDF storage
- CloudFront: CDN for frontend
- Cost: ~$100-300/month

#### **4. Self-Hosted (VPS)**
- Ubuntu 22.04 LTS
- Docker + Docker Compose
- Nginx reverse proxy
- Let's Encrypt SSL
- Cost: $20-80/month (DigitalOcean, Linode)

### Environment Variables (Production)

**Backend (.env):**
```env
# LLM (use cloud provider for production)
OPENAI_API_KEY=your-actual-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Database (use managed PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (for Celery)
REDIS_URL=redis://redis:6379/0

# Storage (use S3 for production)
UPLOAD_DIR=/app/uploads

# Security
SECRET_KEY=generate-random-64-char-string
DEBUG=false

# CORS
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

### Performance Optimization

**Backend:**
- Use PostgreSQL instead of SQLite
- Enable GPU for embeddings (CUDA)
- Cache embedding model in memory
- Use async database queries
- Connection pooling

**Frontend:**
- Build with `npm run build`
- Serve static files from CDN
- Enable compression (gzip/brotli)
- Lazy load routes

**Infrastructure:**
- Use Redis for caching
- Celery workers for async processing
- Load balancer for multiple instances
- Separate embedding service (GPU instance)

### Monitoring

**Recommended Tools:**
- **Logging**: Loguru → CloudWatch/Datadog
- **Metrics**: Prometheus + Grafana
- **Errors**: Sentry
- **Uptime**: UptimeRobot
- **APM**: New Relic / Datadog

---

## Summary

The Annual Report Analyzer is a production-ready AI system that combines:

- **Modern web stack** (React + FastAPI)
- **Local-first ML** (sentence-transformers, Ollama)
- **Hybrid retrieval** (dense + sparse + reranking)
- **Production databases** (PostgreSQL + ChromaDB)
- **Scalable architecture** (async processing, task queues)

It processes financial PDFs end-to-end, extracting structured insights and enabling natural language queries with source citations. The system prioritizes **accuracy**, **explainability**, and **cost-efficiency** through local model deployment and deterministic fallbacks.

**Key Differentiators:**
- ✅ Runs entirely offline (no cloud API dependencies)
- ✅ Indian accounting standards support (INDAS)
- ✅ Deterministic table reader for numeric accuracy
- ✅ Multi-year anomaly detection
- ✅ Source citations on every answer
- ✅ Interactive comparison dashboard
