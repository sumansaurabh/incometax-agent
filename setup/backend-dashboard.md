# Backend And Dashboard

This guide explains how to run the local services that the extension and dashboard depend on.

## What actually matters

1. OpenAI is used for document embeddings and semantic search.
2. The agent runtime uses the Anthropic-compatible client path.
3. Langfuse is optional.

## Prerequisites

1. Docker Desktop or a working local Docker engine
2. Node.js 20+
3. `pnpm`
4. Python 3.10+ if you want to run the backend outside Docker

## Docker Compose path

This is the easiest local setup.

### 1. Create the env file

From the repo root:

```bash
cp infra/docker/.env.example infra/docker/.env
```

Then set at least:

```bash
ITX_OPENAI_API_KEY=your_openai_key
ITX_OPENAI_BASE_URL=https://api.openai.com/v1
ITX_EMBEDDING_MODEL=text-embedding-3-small

ITX_ANTHROPIC_API_KEY=your_anthropic_or_proxy_key
ITX_ANTHROPIC_BASE_URL=http://host.docker.internal:8787
ITX_AGENT_MODEL=bedrock/claude-sonnet-4.6
ITX_AGENT_MODEL_DEEP=bedrock/claude-opus-4.6

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

Expected local URLs:

1. Backend health: `http://localhost:8000/health`
2. Dashboard: `http://localhost:4173`

Notes:

1. The Compose stack exposes `backend` on `8000` and `web-dashboard` on `4173`.
2. Postgres, Redis, Qdrant, and MinIO stay on the internal Docker network by default.
3. `backend` and `workers` bind-mount the source tree, so Python edits reload in local development.

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

If semantic search does not work, check `ITX_OPENAI_API_KEY`, `ITX_EMBEDDING_MODEL`, Qdrant, and MinIO.

If chat or portal assistance does not work, check `ITX_ANTHROPIC_API_KEY`, `ITX_ANTHROPIC_BASE_URL`, `ITX_AGENT_MODEL`, and `ITX_AGENT_MODEL_DEEP`.

## Host-run path

Use this if you want to run the backend and dashboard directly on your host instead of in Docker.

### 1. Make Postgres and Redis available on localhost

The provided Compose file does not publish Postgres or Redis ports by default. For host-run development you need one of these:

1. your own local Postgres and Redis on `localhost:5432` and `localhost:6379`
2. a temporary local Compose override that publishes those ports

### 2. Install dependencies

```bash
pnpm install --no-frozen-lockfile
python -m pip install fastapi uvicorn asyncpg pydantic langgraph opentelemetry-sdk opentelemetry-api opentelemetry-exporter-otlp-proto-http redis anthropic minio pypdf PyMuPDF pillow
```

### 3. Export backend env vars

```bash
export ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx
export ITX_DOCUMENT_STORAGE_ROOT=/tmp/itx-documents
export ITX_REDIS_URL=redis://localhost:6379/0
export ITX_ALLOWED_ORIGINS=http://localhost:4173,http://localhost:5173

export ITX_OPENAI_API_KEY=your_openai_key
export ITX_OPENAI_BASE_URL=https://api.openai.com/v1
export ITX_EMBEDDING_MODEL=text-embedding-3-small

export ITX_ANTHROPIC_API_KEY=your_anthropic_or_proxy_key
export ITX_ANTHROPIC_BASE_URL=http://localhost:8787
export ITX_AGENT_MODEL=bedrock/claude-sonnet-4.6
export ITX_AGENT_MODEL_DEEP=bedrock/claude-opus-4.6
```

Optional:

```bash
export ITX_LANGFUSE_ENABLED=false
export ITX_LANGFUSE_PUBLIC_KEY=
export ITX_LANGFUSE_SECRET_KEY=
export ITX_LANGFUSE_OTLP_ENDPOINT=
```

### 4. Run the backend

The backend imports worker modules directly, so include both source roots on `PYTHONPATH`:

```bash
PYTHONPATH=apps/backend/src:apps/workers/src uvicorn itx_backend.main:app --app-dir apps/backend/src --reload --host 0.0.0.0 --port 8000
```

### 5. Run the dashboard

In a second terminal:

```bash
VITE_ITX_BACKEND_BASE_URL=http://localhost:8000 pnpm --dir apps/web-dashboard dev
```

## Local ports summary

1. `8000`: backend API
2. `4173`: web dashboard
3. `5432`: Postgres if you expose or run it locally
4. `6379`: Redis if you expose or run it locally