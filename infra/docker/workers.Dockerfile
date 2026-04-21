FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/apps/workers/src
COPY apps/workers /app/apps/workers
RUN pip install --no-cache-dir pydantic asyncpg
CMD ["python", "-c", "print('workers-ready')"]
