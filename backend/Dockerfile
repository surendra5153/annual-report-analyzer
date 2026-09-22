FROM python:3.11-slim

# System deps for camelot (ghostscript + opencv) and pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Pre-create data dirs with correct permissions
RUN mkdir -p /app/uploads /app/chroma_db

# Download the embedding model at build time so the first upload isn't slow
# and so the container works offline
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

EXPOSE 8000

# Use exec form so signals (SIGTERM) reach uvicorn, not the shell
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
