# Web Dashboard

CA operations dashboard for reviewer queues, replay health, selector drift, and filing readiness.

## Local usage

```bash
pnpm --dir apps/web-dashboard dev
```

The UI expects the backend to be available with CORS enabled for the dashboard origin. In Docker Compose, the dashboard runs on port `4173` and talks to `http://localhost:8000` by default.
