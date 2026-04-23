FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/apps/backend/src:/app/apps/workers/src
ENV PYTHONUNBUFFERED=1
COPY apps/backend /app/apps/backend
COPY apps/workers /app/apps/workers
RUN apt-get update \
  && apt-get install -y --no-install-recommends tesseract-ocr \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir fastapi uvicorn pydantic opentelemetry-sdk opentelemetry-api opentelemetry-exporter-otlp-proto-http asyncpg redis watchfiles websockets minio pypdf PyMuPDF pillow anthropic
CMD ["uvicorn", "itx_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/apps/backend/src", "--reload-dir", "/app/apps/workers/src"]
