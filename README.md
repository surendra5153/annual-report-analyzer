# Annual Report Analysis System (NLP-07)

AI-powered annual report analysis using Large Language Models — upload a PDF, get structured KPIs, risk flags, footnote inconsistencies, and a chat interface.

## Features
- Multi-modal PDF ingestion (text, tables, charts)
- Adaptive chunking & semantic embeddings
- KPI extraction with deterministic verification (28 canonical KPIs, Indian INDAS aliases)
- Risk classification (financial, regulatory, cyber, climate, supply-chain)
- RAG Q&A with source citations
- **Footnote & Consistency Engine** — cross-checks MD&A vs. notes, prior-year promise tracking
- Anomaly detection & year-over-year trend analysis
- Auto peer discovery via embedding similarity
- React dashboard with chat interface

## Tech Stack
- **Backend**: Python 3.11, FastAPI, Celery
- **PDF/Tables**: PyMuPDF, pdfplumber, Camelot
- **Embeddings**: sentence-transformers (`all-MiniLM-L6-v2`) + ChromaDB
- **LLM**: OpenAI-compatible API (Gemini by default, swappable to OpenAI)
- **DB**: SQLite (dev) / PostgreSQL (prod)
- **Frontend**: React 18 + Vite + Recharts + TailwindCSS
- **Scheduler**: Celery + Redis

---

## Local Development

```bash
# 1. Clone
git clone <repo-url>
cd annual-report-analyzer

# 2. Backend
cd backend
pip install -r requirements-local.txt
cp .env.example .env
# Edit .env — set OPENAI_API_KEY (Gemini key from aistudio.google.com/apikey)
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### Getting a Free Gemini API Key
1. Go to https://aistudio.google.com/apikey
2. Click **"Create API key"**
3. Copy the key (starts with `AIza...`)
4. Paste into `backend/.env` as `OPENAI_API_KEY=AIza...`

---

## Deployment

### Option A — Railway (Recommended, free tier available)

Railway runs the full Docker Compose stack (backend + PostgreSQL + Redis + frontend).

**Step 1 — Push to GitHub**
```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/annual-report-analyzer.git
git push -u origin main
```

**Step 2 — Deploy on Railway**
1. Go to https://railway.app → **"New Project"** → **"Deploy from GitHub repo"**
2. Select your repo

**Step 3 — Add services on Railway**

Railway doesn't auto-read `docker-compose.yml` as multiple services, so add them manually:

- **Backend service**: point to `/backend` folder, Dockerfile detected automatically
- **PostgreSQL**: click **"Add Service"** → **"Database"** → **"PostgreSQL"**
- **Redis**: click **"Add Service"** → **"Database"** → **"Redis"**
- **Frontend service**: point to `/frontend` folder, Dockerfile detected automatically

**Step 4 — Set environment variables on the Backend service**

In Railway → Backend service → Variables tab, add:
```
OPENAI_API_KEY=AIza...your-gemini-key
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_MODEL=gemini-3.5-flash-lite
OPENAI_VISION_MODEL=gemini-3.5-flash-lite
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
SECRET_KEY=your-random-secret-key
DEBUG=false
CORS_ORIGINS=["https://your-frontend.railway.app"]
UPLOAD_DIR=./uploads
CHROMA_LOCAL_PATH=./chroma_db
ENABLE_VISION_EXTRACTION=false
```

> **Tip**: Railway injects `${{Postgres.DATABASE_URL}}` and `${{Redis.REDIS_URL}}` automatically when you link the services.

**Step 5 — Set frontend environment (optional)**

If you want the frontend to hit a specific backend URL directly, set:
```
VITE_API_URL=https://your-backend.railway.app
```

**Step 6 — Deploy**

Railway auto-deploys on every push to `main`. Your app will be live at the Railway-provided `.railway.app` URLs.

---

### Option B — Render (free tier, slower cold starts)

**Backend:**
1. Go to https://render.com → **"New Web Service"** → connect GitHub repo
2. Root directory: `backend`
3. Runtime: **Docker**
4. Add the same environment variables as above
5. Add a **PostgreSQL** database from Render dashboard — copy the connection string to `DATABASE_URL`

**Frontend:**
1. New **Static Site** → connect same repo
2. Root directory: `frontend`
3. Build command: `npm install && npm run build`
4. Publish directory: `dist`
5. Add env var: `VITE_API_URL=https://your-backend.onrender.com`

**Note:** Update `frontend/src/services/api.js` baseURL when using separate domains (see below).

---

### Option C — Docker Compose on a VPS (DigitalOcean / Hetzner / any Linux VM)

```bash
# On your server
git clone <repo-url>
cd annual-report-analyzer

# Create backend/.env from the example
cp backend/.env.example backend/.env
nano backend/.env   # fill in your API key and a real SECRET_KEY

# Build and run everything
docker compose up -d --build

# Check logs
docker compose logs -f backend
```

Services will be available at:
- Frontend: `http://YOUR_SERVER_IP:3000`
- Backend API: `http://YOUR_SERVER_IP:8000`
- API docs: `http://YOUR_SERVER_IP:8000/api/docs`
- Flower (Celery monitor): `http://YOUR_SERVER_IP:5555`

For HTTPS, put Nginx + Certbot in front (or use Caddy).

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | Gemini or OpenAI API key |
| `OPENAI_BASE_URL` | Gemini only | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `OPENAI_MODEL` | ✅ | `gemini-3.5-flash-lite` or `gpt-4o-mini` |
| `DATABASE_URL` | ✅ | PostgreSQL or SQLite URL |
| `SECRET_KEY` | ✅ | Random string for production |
| `REDIS_URL` | Celery only | Redis connection URL |
| `CORS_ORIGINS` | ✅ | JSON array of allowed frontend origins |
| `UPLOAD_DIR` | | Path to store uploaded PDFs (default `./uploads`) |
| `CHROMA_LOCAL_PATH` | | Path for ChromaDB data (default `./chroma_db`) |
| `ENABLE_VISION_EXTRACTION` | | `true/false` — uses extra LLM tokens (default `false`) |
| `DEBUG` | | `false` in production |
