# Backend And Dashboard

This guide explains how to run the local services that the extension and dashboard depend on.

## What you are starting

1. Postgres on `localhost:5432`
2. Redis on `localhost:6379`
3. Backend API on `localhost:8000`
4. Web dashboard on `localhost:4173`

## Prerequisites

1. Docker Desktop or a working local Docker engine
2. Node.js 20+
3. `pnpm`
4. Python 3.10+ if you want to run the backend outside Docker

## Mandatory env keys

There are two different levels of configuration in this repo.

Minimum required for the backend to boot:

1. `ITX_DATABASE_URL`: Postgres connection string
2. `ITX_DOCUMENT_STORAGE_ROOT`: writable folder for uploaded and generated artifacts

Required with the current local Docker setup because AI is enabled by default:

1. `ITX_AI_PROVIDER`
2. `ITX_AI_MODEL`
3. `ITX_AI_API_KEY`

Required only if you explicitly enable Langfuse tracing:

1. `ITX_LANGFUSE_ENABLED=true`
2. `ITX_LANGFUSE_PUBLIC_KEY`
3. `ITX_LANGFUSE_SECRET_KEY`
4. `ITX_LANGFUSE_OTLP_ENDPOINT` or `ITX_OTEL_EXPORTER_OTLP_ENDPOINT`

Required for the dashboard frontend:

1. `VITE_ITX_BACKEND_BASE_URL`

Important: the backend startup health check fails if `ITX_AI_PROVIDER` is set but `ITX_AI_API_KEY` is empty. The current Compose file defaults `ITX_AI_PROVIDER=openai`, so you must set a real API key in `infra/docker/.env` before starting the stack.

## Option A: run with Docker Compose

This is the easiest local path.

### 1. Create the env file

From the repo root:

```bash
cp infra/docker/.env.example infra/docker/.env
```

Then edit `infra/docker/.env` and set at least:

```bash
ITX_AI_PROVIDER=openai
ITX_AI_MODEL=gpt-4.1-mini
ITX_AI_API_KEY=your_real_provider_key

ITX_LANGFUSE_ENABLED=false

ITX_REDIS_URL=redis://redis:6379/0
ITX_ALLOWED_ORIGINS=http://localhost:4173,http://localhost:5173
VITE_ITX_BACKEND_BASE_URL=http://localhost:8000
```

Optional Langfuse tracing:

```bash
ITX_LANGFUSE_ENABLED=true
ITX_LANGFUSE_PUBLIC_KEY=pk_...
ITX_LANGFUSE_SECRET_KEY=sk_...
ITX_LANGFUSE_OTLP_ENDPOINT=https://your-langfuse-otlp-endpoint
```

### 2. Start the stack

From the repo root:

```bash
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up --build
```

This Compose setup is now development-oriented:

1. `backend` hot reloads on Python changes under `apps/backend` and `apps/workers`
2. `workers` hot reloads on Python changes under `apps/backend` and `apps/workers`
3. `web-dashboard` uses Vite dev mode with bind-mounted source for live reload

Expected local URLs:

1. Backend health: `http://localhost:8000/health`
2. Dashboard: `http://localhost:4173`

Notes:

1. Backend startup automatically initializes the DB pool and applies SQL migrations from `apps/backend/src/itx_backend/db/migrations`
2. Redis is used for runtime cache and event buffering when available
3. The current `workers` container is only a readiness stub and is not the main local interaction surface yet

### 3. Verify the backend is healthy

Open:

```text
http://localhost:8000/health
```

You want to see:

1. database check `ok`
2. document storage check `ok`
3. configuration check `ok`
4. observability check `ok`

If observability fails, the first thing to check is whether `ITX_AI_API_KEY` is missing while `ITX_AI_PROVIDER` is set.

## Option B: run backend and dashboard directly on your host

Use this if you want a faster edit-refresh loop.

### 1. Start Postgres and Redis only

```bash
docker compose -f infra/docker/docker-compose.yml up -d postgres redis
```

### 2. Install JS dependencies

```bash
pnpm install --no-frozen-lockfile
```

### 3. Install Python dependencies

One simple path is:

```bash
python -m pip install fastapi uvicorn asyncpg pydantic langgraph opentelemetry-sdk opentelemetry-api opentelemetry-exporter-otlp-proto-http redis
```

### 4. Export local backend env vars

```bash
export ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx
export ITX_DOCUMENT_STORAGE_ROOT=/tmp/itx-documents
export ITX_REDIS_URL=redis://localhost:6379/0
export ITX_ALLOWED_ORIGINS=http://localhost:4173,http://localhost:5173

export ITX_AI_PROVIDER=openai
export ITX_AI_MODEL=gpt-4.1-mini
export ITX_AI_API_KEY=your_real_provider_key
```

Optional:

```bash
export ITX_LANGFUSE_ENABLED=false
export ITX_LANGFUSE_PUBLIC_KEY=
export ITX_LANGFUSE_SECRET_KEY=
export ITX_LANGFUSE_OTLP_ENDPOINT=
```

### 5. Run the backend

The backend imports worker modules directly, so include both source roots on `PYTHONPATH`:

```bash
PYTHONPATH=apps/backend/src:apps/workers/src uvicorn itx_backend.main:app --app-dir apps/backend/src --reload --host 0.0.0.0 --port 8000
```

### 6. Run the dashboard

In a second terminal:

```bash
VITE_ITX_BACKEND_BASE_URL=http://localhost:8000 pnpm --dir apps/web-dashboard dev
```

## Local ports summary

1. `5432`: Postgres
2. `6379`: Redis
3. `8000`: backend API
4. `4173`: web dashboard