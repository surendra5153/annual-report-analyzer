# Annual Report Analyzer

AI-powered annual report analysis system that processes PDF financial reports to extract structured insights, detect risks, and provide an interactive Q&A interface.

## Project Overview

This application uses Large Language Models to analyze corporate annual reports and financial filings. It automatically extracts key performance indicators (KPIs), identifies risks, detects anomalies, and enables natural language queries about the reports through a web-based dashboard.

### Key Features

- **PDF Processing** — Multi-modal ingestion of text, tables, and charts from annual reports
- **KPI Extraction** — Automatically extracts 28 canonical financial KPIs with Indian INDAS support
- **Risk Analysis** — Classifies risks into categories: financial, regulatory, cyber, climate, supply-chain
- **RAG Q&A** — Ask questions about reports with source citations
- **Financial Comparison** — Compare up to 3 companies side-by-side (Revenue, Expenses, Profit)
- **Anomaly Detection** — Year-over-year trend analysis and inconsistency checking
- **Peer Discovery** — Finds similar companies using embedding similarity
- **Live Dashboard** — Real-time metrics, risk feed, and processing status

### Technology Stack

- **Backend**: Python 3.11+, FastAPI, Celery, SQLite/PostgreSQL
- **PDF Processing**: PyMuPDF, pdfplumber, Camelot
- **ML/AI**: sentence-transformers, ChromaDB, OpenAI-compatible LLM API
- **Frontend**: React 18, Vite, TailwindCSS, Recharts, React Query
- **Task Queue**: Celery + Redis

## Setup Instructions

### Prerequisites

- Python 3.12+ ([python.org](https://python.org))
- Node.js 18+ ([nodejs.org](https://nodejs.org))
- Ollama 0.35+ ([ollama.com/download](https://ollama.com/download)) — for local LLM
- NVIDIA GPU (optional, improves performance)

### Local Setup

**1. Install Ollama and Download Models**

```bash
# Download and install Ollama from ollama.com
# Then download the LLM model
ollama pull qwen2.5:3b
ollama create finsight-qwen -f ml/export/Modelfile.finsight-qwen
ollama list  # verify models are installed
```

**2. Setup Backend**

```bash
cd backend

# Install dependencies
pip install -r requirements-local.txt

# Optional: For GPU acceleration (NVIDIA only)
pip install torch --index-url https://download.pytorch.org/whl/cu130

# Start the backend server
python -m uvicorn app.main:app --reload --port 8000
```

The backend runs at `http://localhost:8000`. API docs available at `http://localhost:8000/api/docs`.

**3. Setup Frontend**

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend runs at `http://localhost:3000`.

### Quick Start (After Initial Setup)

```bash
# Terminal 1 - Backend
cd backend && python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend && npm run dev
```

Open `http://localhost:3000` in your browser.

### Configuration

The application works with default settings (SQLite database, local Ollama, ChromaDB). To customize, create `backend/.env`:

```env
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///./annual_reports.db
```

### Troubleshooting

- **Port already in use**: Another instance is running. Stop it or use the running instance.
- **Ollama connection refused**: Ensure Ollama is running (`ollama serve`).
- **Model not found**: Run `ollama create finsight-qwen -f ml/export/Modelfile.finsight-qwen`.
- **Slow embedding**: Install GPU version of PyTorch or ensure CUDA is available.

## Deployment Options

### Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repo-url>
cd annual-report-analyzer

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys and configuration

# Build and run
docker compose up -d --build

# View logs
docker compose logs -f backend
```

Services will be available at:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/api/docs`

### Cloud Deployment

**Railway**
1. Push code to GitHub
2. Create new Railway project from GitHub repo
3. Add services: Backend, Frontend, PostgreSQL, Redis
4. Configure environment variables in Backend service
5. Auto-deploys on push to main

**Render**
1. Create Web Service for backend (Docker runtime)
2. Create Static Site for frontend
3. Add PostgreSQL database
4. Configure environment variables

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | API key for LLM (Gemini or OpenAI) |
| `OPENAI_BASE_URL` | No | API base URL (for Gemini) |
| `OPENAI_MODEL` | Yes | Model name (e.g., `gemini-3.5-flash-lite`) |
| `DATABASE_URL` | Yes | PostgreSQL or SQLite connection string |
| `SECRET_KEY` | Yes | Random secret for production |
| `REDIS_URL` | No | Redis connection (for Celery) |
| `CORS_ORIGINS` | Yes | JSON array of allowed frontend origins |
| `DEBUG` | No | Set to `false` in production |
