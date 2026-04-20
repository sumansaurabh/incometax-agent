from fastapi import FastAPI

from itx_backend.api import actions, auth, documents, tax_facts, threads, websocket
from itx_backend.config import settings
from itx_backend.telemetry.tracing import setup_tracing


def create_app() -> FastAPI:
    setup_tracing()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(auth.router)
    app.include_router(threads.router)
    app.include_router(documents.router)
    app.include_router(actions.router)
    app.include_router(tax_facts.router)
    app.include_router(websocket.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
