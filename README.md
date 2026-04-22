# IncomeTax Agent

AI copilot for Indian Income Tax e-Filing portal. See docs/ for full plan and architecture.

If you want to run the stack locally, start with the guides in setup/.

## Runtime Configuration

The backend now exposes explicit env vars for AI-provider wiring, Langfuse-compatible OTLP tracing, and Redis-backed runtime state.

### AI provider key

Set these before starting the backend:

```bash
export ITX_AI_PROVIDER=openai
export ITX_AI_MODEL=gpt-4.1-mini
export ITX_AI_API_KEY=your-provider-key
```

Optional:

```bash
export ITX_AI_BASE_URL=https://your-provider-base-url
```

### Langfuse-compatible tracing

If you want traces exported to Langfuse via OTLP, set:

```bash
export ITX_LANGFUSE_ENABLED=true
export ITX_LANGFUSE_PUBLIC_KEY=pk_live_or_pk_test
export ITX_LANGFUSE_SECRET_KEY=sk_live_or_sk_test
export ITX_LANGFUSE_OTLP_ENDPOINT=https://your-langfuse-otlp-endpoint
```

### Redis runtime state

To move rate limiting and agent-event buffering off in-process memory:

```bash
export ITX_REDIS_URL=redis://localhost:6379/0
export ITX_REDIS_KEY_PREFIX=itx
```

The `/health` response now reports runtime cache, tracing, AI-provider, and observability configuration status so you can verify the setup quickly.
