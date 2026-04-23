# IncomeTax Agent

AI copilot for the Indian Income Tax e-Filing portal. The local stack has three main pieces:

- **Backend + workers** — FastAPI plus Python workers for document intake, parsing, indexing, retrieval, and agent execution.
- **Web dashboard** — Vite app at `http://localhost:4173`.
- **Chrome extension** — injected sidepanel for the e-Filing portal.

Supporting infra (Postgres, Redis, Qdrant, MinIO) runs through Docker Compose.

## What Actually Uses Which Model

This is the important part for this repo as it exists today:

- **OpenAI is used for embeddings**, which power document indexing and semantic search.
- **The tax agent itself uses the Anthropic-compatible client path**, configured through `ITX_ANTHROPIC_*` and `ITX_AGENT_MODEL*`.
- **Langfuse is optional** and not required for local development.

## Prerequisites

- Docker and Docker Compose
- Node.js 18+ and `pnpm`
- An Anthropic-compatible API key/endpoint for agent chat and reasoning
- An OpenAI API key for embeddings and semantic search

## 1. Configure `infra/docker/.env`

This stack reads backend and worker env vars from `infra/docker/.env`.

Use this as the practical local setup for this service:

```env
# OpenAI: used for embeddings and semantic document search.
ITX_OPENAI_API_KEY=sk-...
ITX_OPENAI_BASE_URL=https://api.openai.com/v1
ITX_EMBEDDING_MODEL=text-embedding-3-small

# Agent runtime: Anthropic-compatible endpoint.
ITX_ANTHROPIC_API_KEY=ank_...
ITX_ANTHROPIC_BASE_URL=http://host.docker.internal:8787
ITX_AGENT_MODEL=bedrock/claude-sonnet-4.6
ITX_AGENT_MODEL_DEEP=bedrock/claude-opus-4.6

# Local app wiring.
ITX_REDIS_URL=redis://redis:6379/0
ITX_ALLOWED_ORIGINS=http://localhost:4173,http://localhost:5173
VITE_ITX_BACKEND_BASE_URL=http://localhost:8000
```

Notes:

- `ITX_EMBEDDING_MODEL` is the OpenAI model that matters for document indexing and semantic search.
- `ITX_AGENT_MODEL` and `ITX_AGENT_MODEL_DEEP` are the agent reasoning models that matter for chat and portal assistance.
- If `ITX_OPENAI_API_KEY` is missing, parsing can still proceed, but embedding-backed indexing/search will degrade or be skipped.

Optional keys if you want those capabilities:

```env
ITX_COHERE_API_KEY=...
ITX_TAVILY_API_KEY=...
```

Langfuse is optional. Leave it off unless you actively want tracing:

```env
ITX_LANGFUSE_ENABLED=false
ITX_LANGFUSE_PUBLIC_KEY=
ITX_LANGFUSE_SECRET_KEY=
ITX_LANGFUSE_OTLP_ENDPOINT=
ITX_OTEL_EXPORTER_OTLP_ENDPOINT=
ITX_OTEL_EXPORTER_OTLP_HEADERS=
```

## 2. Start the local stack

From the repo root, run:

```bash
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up --build
```

This starts:

| Service | Port | Purpose |
| --- | --- | --- |
| backend | `8000` | API, agent runtime, document endpoints |
| workers | — | background parsing and indexing |
| web-dashboard | `4173` | local dashboard |
| postgres | internal | primary database |
| redis | internal | cache and runtime coordination |
| qdrant | internal | vector store for semantic search |
| minio | internal | S3-compatible document storage |

Useful checks:

- Backend health: <http://localhost:8000/health>
- Dashboard: <http://localhost:4173>

Stop the stack with:

```bash
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml down
```

Add `-v` if you want to wipe Qdrant and MinIO volumes.

## 3. Build the Chrome extension

From the repo root:

```bash
pnpm install
pnpm --dir apps/extension build
```

Load the built extension in Chrome:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select `apps/extension/dist`.

The extension talks to the backend through `VITE_ITX_BACKEND_BASE_URL`, which is `http://localhost:8000` in the local setup above. If you change that value, rebuild the extension.

For local extension iteration:

```bash
pnpm --dir apps/extension dev
```

## 4. Common commands

```bash
# Backend logs
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml logs -f backend

# Worker logs
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml logs -f workers

# Rebuild only the backend
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up --build backend
```

The backend and workers are bind-mounted in Docker, so Python changes reload inside the containers during local development.

## 5. Troubleshooting

- If document upload works but semantic search/indexing does not, check `ITX_OPENAI_API_KEY`, `ITX_EMBEDDING_MODEL`, Qdrant, and MinIO.
- If chat or portal-assistance flows fail, check `ITX_ANTHROPIC_API_KEY`, `ITX_ANTHROPIC_BASE_URL`, `ITX_AGENT_MODEL`, and `ITX_AGENT_MODEL_DEEP`.
- If you do not care about tracing, keep Langfuse disabled.
- If Qdrant or MinIO gets stuck on startup, bring the stack down with `-v` and start again.
