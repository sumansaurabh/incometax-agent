from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import asyncpg

from itx_backend.config import settings


_pool: Optional[asyncpg.Pool] = None
_pool_lock: Optional[asyncio.Lock] = None
_pool_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_pool_lock() -> asyncio.Lock:
    current_loop = asyncio.get_running_loop()
    global _pool_lock
    if _pool_lock is None or getattr(_pool_lock, "_loop", current_loop) is not current_loop:
        _pool_lock = asyncio.Lock()
    return _pool_lock


async def apply_migrations(pool: asyncpg.Pool) -> None:
    migration_dir = Path(__file__).with_name("migrations")
    migration_paths = sorted(migration_dir.glob("*.sql"))
    if not migration_paths:
        return

    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                create table if not exists schema_migrations (
                    version text primary key,
                    applied_at timestamptz not null default now()
                )
                """
            )
            applied_rows = await connection.fetch("select version from schema_migrations")
            applied_versions = {row["version"] for row in applied_rows}

            for migration_path in migration_paths:
                if migration_path.name in applied_versions:
                    continue
                await connection.execute(migration_path.read_text(encoding="utf-8"))
                await connection.execute(
                    "insert into schema_migrations (version) values ($1)",
                    migration_path.name,
                )


async def init_connection_pool() -> asyncpg.Pool:
    global _pool, _pool_loop
    current_loop = asyncio.get_running_loop()
    if _pool is not None and _pool_loop is current_loop:
        return _pool

    async with _get_pool_lock():
        if _pool is None or _pool_loop is not current_loop:
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=settings.database_min_pool_size,
                max_size=settings.database_max_pool_size,
            )
            _pool_loop = current_loop
            await apply_migrations(_pool)
    return _pool


async def get_pool() -> asyncpg.Pool:
    if _pool is None or _pool_loop is not asyncio.get_running_loop():
        return await init_connection_pool()
    return _pool


async def close_connection_pool() -> None:
    global _pool, _pool_loop
    if _pool is None:
        return

    pool = _pool
    _pool = None
    _pool_loop = None
    await pool.close()
