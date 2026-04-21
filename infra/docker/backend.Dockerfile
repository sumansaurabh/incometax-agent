FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/apps/backend/src:/app/apps/workers/src
COPY apps/backend /app/apps/backend
COPY apps/workers /app/apps/workers
RUN pip install --no-cache-dir fastapi uvicorn pydantic opentelemetry-sdk opentelemetry-api asyncpg
CMD ["uvicorn", "itx_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
