FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/apps/backend/src:/app/apps/workers/src
ENV PYTHONUNBUFFERED=1
COPY apps/backend /app/apps/backend
COPY apps/workers /app/apps/workers
RUN apt-get update \
  && apt-get install -y --no-install-recommends tesseract-ocr \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir pydantic asyncpg redis watchfiles minio pypdf PyMuPDF pillow anthropic
CMD ["python", "-m", "itx_workers.dev_runner"]
