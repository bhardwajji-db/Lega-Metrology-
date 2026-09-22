FROM python:3.11-slim

# Install system dependencies: tesseract-ocr, opencv libs, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    fonts-dejavu \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend

# Install Python dependencies (cloud / no-paddle requirements)
COPY backend/requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copy backend application source code
COPY backend/ .

# Ensure data and uploads directory exist
RUN mkdir -p /data/uploads

# Container runtime configuration
ENV PYTHONUNBUFFERED=1 \
    OCR_ENGINE=tesseract \
    METRCHECK_DEMO_MODE=true \
    UPLOAD_DIR=/data/uploads \
    DATABASE_PATH=/data/metrc_check.db

EXPOSE 8000

# Health check via /api/health
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

