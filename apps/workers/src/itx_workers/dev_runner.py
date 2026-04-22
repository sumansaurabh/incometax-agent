from __future__ import annotations

import asyncio
import os
from pathlib import Path

from watchfiles import PythonFilter, run_process

from itx_backend.db.session import close_connection_pool, init_connection_pool
from itx_backend.services.documents import document_service
from itx_backend.services.runtime_cache import runtime_cache


PROJECT_ROOT = Path(__file__).resolve().parents[4]
WATCH_PATHS = (
    str(PROJECT_ROOT / "apps" / "backend" / "src"),
    str(PROJECT_ROOT / "apps" / "workers" / "src"),
)
POLL_INTERVAL_SECONDS = float(os.getenv("ITX_WORKER_POLL_INTERVAL_SECONDS", "1"))


async def run_forever() -> None:
    await init_connection_pool()
    try:
        while True:
            try:
                processed = await document_service.process_pending_jobs()
                if processed:
                    print(f"workers processed {len(processed)} job(s)", flush=True)
                    continue
            except Exception as exc:
                print(f"workers loop error: {exc}", flush=True)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await runtime_cache.close()
        await close_connection_pool()


def _serve() -> None:
    asyncio.run(run_forever())


def main() -> None:
    run_process(*WATCH_PATHS, target=_serve, watch_filter=PythonFilter())


if __name__ == "__main__":
    main()