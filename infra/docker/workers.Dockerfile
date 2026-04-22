FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/apps/backend/src:/app/apps/workers/src
ENV PYTHONUNBUFFERED=1
COPY apps/backend /app/apps/backend
COPY apps/workers /app/apps/workers
RUN pip install --no-cache-dir pydantic asyncpg redis watchfiles
CMD ["python", "-m", "itx_workers.dev_runner"]
