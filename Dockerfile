FROM python:3.11-slim

# Install system dependencies for PaddleOCR, OpenCV, and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libstdc++6 \
    fonts-dejavu \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY backend/ .

# Container runtime configuration
ENV PYTHONUNBUFFERED=1 \
    OCR_ENGINE=paddleocr \
    UPLOAD_DIR=/data/uploads \
    DATABASE_PATH=/data/metrc_check.db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
