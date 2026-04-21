from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from itx_backend.config import settings
from itx_backend.db.session import get_pool


class StartupHealthService:
    def __init__(self) -> None:
        self._snapshot: dict[str, Any] = {
            "status": "unknown",
            "generated_at": None,
            "checks": [],
        }

    async def validate_startup(self) -> dict[str, Any]:
        snapshot = await self.run_checks()
        failures = [check for check in snapshot["checks"] if check["status"] != "ok"]
        self._snapshot = snapshot
        if failures:
            failed_names = ", ".join(check["name"] for check in failures)
            raise RuntimeError(f"startup health checks failed: {failed_names}")
        return snapshot

    async def run_checks(self) -> dict[str, Any]:
        checks = [
            await self._check_database(),
            await self._check_document_storage(),
            self._check_configuration(),
        ]
        status = "ok" if all(check["status"] == "ok" for check in checks) else "degraded"
        snapshot = {
            "status": status,
            "environment": settings.environment,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        }
        self._snapshot = snapshot
        return snapshot

    def latest(self) -> dict[str, Any]:
        return self._snapshot

    async def _check_database(self) -> dict[str, Any]:
        try:
            pool = await get_pool()
            async with pool.acquire() as connection:
                value = await connection.fetchval("select 1")
            return {
                "name": "database",
                "status": "ok" if value == 1 else "degraded",
                "detail": "connection pool initialized and query succeeded",
            }
        except Exception as exc:  # pragma: no cover
            return {
                "name": "database",
                "status": "failed",
                "detail": str(exc),
            }

    async def _check_document_storage(self) -> dict[str, Any]:
        root = Path(settings.document_storage_root)
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".healthcheck"
            await asyncio.to_thread(probe.write_text, "ok", encoding="utf-8")
            await asyncio.to_thread(probe.unlink)
            return {
                "name": "document_storage",
                "status": "ok",
                "detail": f"document root writable at {root}",
            }
        except Exception as exc:  # pragma: no cover
            return {
                "name": "document_storage",
                "status": "failed",
                "detail": str(exc),
            }

    def _check_configuration(self) -> dict[str, Any]:
        issues: list[str] = []
        if settings.database_min_pool_size <= 0:
            issues.append("database_min_pool_size must be positive")
        if settings.database_max_pool_size < settings.database_min_pool_size:
            issues.append("database_max_pool_size must be >= database_min_pool_size")
        if settings.document_upload_ttl_seconds <= 0:
            issues.append("document_upload_ttl_seconds must be positive")
        if settings.auth_access_ttl_seconds <= 0 or settings.auth_refresh_ttl_seconds <= 0:
            issues.append("auth TTLs must be positive")
        if settings.retention_purge_days <= 0:
            issues.append("retention_purge_days must be positive")
        if settings.environment == "prod" and settings.document_upload_secret == "dev-document-upload-secret":
            issues.append("document_upload_secret must not use the development default in prod")

        return {
            "name": "configuration",
            "status": "ok" if not issues else "failed",
            "detail": "configuration validated" if not issues else "; ".join(issues),
        }


startup_health_service = StartupHealthService()