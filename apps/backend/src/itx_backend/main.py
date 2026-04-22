from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from itx_backend.api import (
    actions,
    analytics,
    autopilot,
    auth,
    ca_workspace,
    chat,
    documents,
    drift,
    exports,
    filing,
    replay,
    security,
    tax_facts,
    threads,
    websocket,
)
from itx_backend.config import settings
from itx_backend.db.session import close_connection_pool, init_connection_pool
from itx_backend.security.anomaly import anomaly_detector
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.security.rate_limit import FixedWindowRateLimiter
from itx_backend.services.auth_runtime import AuthError, auth_runtime
from itx_backend.services.document_storage import document_storage
from itx_backend.services.retention import retention_service
from itx_backend.services.runtime_cache import runtime_cache
from itx_backend.services.startup_health import startup_health_service
from itx_backend.telemetry.tracing import setup_tracing


limiter = FixedWindowRateLimiter(limit=500, window_seconds=settings.rate_limit_window_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_connection_pool()
    ensure_bucket = getattr(document_storage, "ensure_bucket", None)
    if callable(ensure_bucket):
        ensure_bucket()
    await startup_health_service.validate_startup()
    try:
        yield
    finally:
        await runtime_cache.close()
        await close_connection_pool()


def create_app() -> FastAPI:
    setup_tracing()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    allowed_origins = [origin.strip() for origin in settings.allowed_origins_csv.split(",") if origin.strip()]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        key = request.client.host if request.client else "unknown"
        if not await limiter.allow(key):
            return JSONResponse(content={"error": "rate_limited"}, status_code=429)

        anomalies = anomaly_detector.observe(
            key=key,
            action=request.url.path,
        )
        auth_token = None
        # Only these auth endpoints are unauthenticated. /me and /revoke must run
        # through the same middleware pipeline so a single auth path governs them.
        unauthenticated_auth_paths = {
            "/api/auth/login",
            "/api/auth/signup",
            "/api/auth/refresh",
        }
        if request.url.path.startswith("/api/") and request.url.path not in unauthenticated_auth_paths:
            authorization = request.headers.get("Authorization")
            access_token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else request.query_params.get("access_token")
            device_id = request.headers.get("X-ITX-Device-ID") or request.query_params.get("device_id", "")
            if not access_token:
                return JSONResponse(content={"error": "authorization_required"}, status_code=401)
            try:
                auth_context = await auth_runtime.authenticate_access_token(
                    access_token,
                    device_id,
                )
                auth_token = set_request_auth(auth_context)
            except AuthError as exc:
                return JSONResponse(content={"error": exc.code}, status_code=exc.status_code)

        try:
            await retention_service.maybe_run_due_purges()
            response = await call_next(request)
        finally:
            if auth_token is not None:
                reset_request_auth(auth_token)

        if anomalies:
            response.headers["X-Anomaly-Detected"] = "true"
        return response

    app.include_router(auth.router)
    app.include_router(threads.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(actions.router)
    app.include_router(analytics.router)
    app.include_router(drift.router)
    app.include_router(autopilot.router)
    app.include_router(replay.router)
    app.include_router(exports.router)
    app.include_router(filing.router)
    app.include_router(ca_workspace.router)
    app.include_router(security.router)
    app.include_router(tax_facts.router)
    app.include_router(websocket.router)

    @app.get("/health")
    async def health() -> dict[str, object]:
        return await startup_health_service.run_checks()

    return app


app = create_app()
