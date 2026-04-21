from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from itx_backend.api import (
    actions,
    analytics,
    autopilot,
    auth,
    ca_workspace,
    documents,
    drift,
    exports,
    replay,
    security,
    tax_facts,
    threads,
    websocket,
)
from itx_backend.config import settings
from itx_backend.db.session import close_connection_pool, init_connection_pool
from itx_backend.security.anomaly import anomaly_detector
from itx_backend.security.rate_limit import FixedWindowRateLimiter
from itx_backend.telemetry.tracing import setup_tracing


limiter = FixedWindowRateLimiter(limit=500)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_connection_pool()
    try:
        yield
    finally:
        await close_connection_pool()


def create_app() -> FastAPI:
    setup_tracing()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        key = request.client.host if request.client else "unknown"
        if not limiter.allow(key):
            return JSONResponse(content={"error": "rate_limited"}, status_code=429)

        anomalies = anomaly_detector.observe(
            key=key,
            action=request.url.path,
        )
        response = await call_next(request)
        if anomalies:
            response.headers["X-Anomaly-Detected"] = "true"
        return response

    app.include_router(auth.router)
    app.include_router(threads.router)
    app.include_router(documents.router)
    app.include_router(actions.router)
    app.include_router(analytics.router)
    app.include_router(drift.router)
    app.include_router(autopilot.router)
    app.include_router(replay.router)
    app.include_router(exports.router)
    app.include_router(ca_workspace.router)
    app.include_router(security.router)
    app.include_router(tax_facts.router)
    app.include_router(websocket.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
