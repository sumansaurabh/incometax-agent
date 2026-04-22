# Local Setup

This folder is the practical local-run guide for the repo.

Products in this repo:

1. Backend API: FastAPI service on `http://localhost:8000`
2. Web dashboard: CA/reviewer dashboard on `http://localhost:4173`
3. Chrome extension: unpacked MV3 extension that runs against the live income tax portal and the local backend
4. Postgres and Redis: local infrastructure used by the backend

Use these guides in order:

1. [backend-dashboard.md](./backend-dashboard.md): start Postgres, Redis, backend, and dashboard; includes mandatory env keys
2. [chrome-extension.md](./chrome-extension.md): build and load the Chrome extension locally
3. [how-to-use.md](./how-to-use.md): sign in, create a filing thread, and use the extension and dashboard together

## Recommended local path

For the least friction, use Docker Compose for infrastructure and backend, then load the Chrome extension from a local build:

1. Copy `infra/docker/.env.example` to `infra/docker/.env`
2. Fill the mandatory keys described in [backend-dashboard.md](./backend-dashboard.md)
3. Run Docker Compose from the repo root
4. Build and load the extension from `apps/extension/dist`

If you prefer to run the backend and dashboard directly on your host machine instead of Docker, the same guide covers that path too.