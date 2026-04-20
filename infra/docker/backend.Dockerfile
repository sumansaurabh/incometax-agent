FROM python:3.11-slim
WORKDIR /app
COPY apps/backend /app/apps/backend
RUN pip install fastapi uvicorn pydantic
CMD ["uvicorn", "itx_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
