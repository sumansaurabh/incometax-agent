from __future__ import annotations

from collections import defaultdict
import json
import time
from typing import Any, Optional

from itx_backend.config import settings

try:  # pragma: no cover - optional dependency
    from redis.asyncio import Redis
except Exception:  # pragma: no cover - import guard for local/test environments
    Redis = None  # type: ignore[assignment]


class RuntimeCache:
    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._counters: dict[str, int] = {}
        self._lists: dict[str, list[str]] = defaultdict(list)

    def backend(self) -> str:
        if settings.redis_url and Redis is not None:
            return "redis"
        return "memory"

    def _key(self, key: str) -> str:
        return f"{settings.redis_key_prefix}:{key}"

    async def _get_client(self) -> Optional[Any]:
        if not settings.redis_url or Redis is None:
            return None
        if self._client is None:
            self._client = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def ping(self) -> dict[str, Any]:
        client = await self._get_client()
        if client is None:
            return {
                "status": "ok",
                "backend": "memory",
                "detail": "Redis not configured; using in-memory runtime cache.",
            }
        try:
            await client.ping()
            return {
                "status": "ok",
                "backend": "redis",
                "detail": "Redis runtime cache reachable.",
            }
        except Exception as exc:  # pragma: no cover - network failure path
            return {
                "status": "failed",
                "backend": "redis",
                "detail": str(exc),
            }

    async def increment_window(self, key: str, window_seconds: int) -> int:
        bucket = int(time.time() // max(window_seconds, 1))
        window_key = self._key(f"window:{key}:{bucket}")
        client = await self._get_client()
        if client is not None:
            value = int(await client.incr(window_key))
            if value == 1:
                await client.expire(window_key, max(window_seconds * 2, 1))
            return value

        value = self._counters.get(window_key, 0) + 1
        self._counters[window_key] = value
        return value

    async def append_json(self, key: str, payload: dict[str, Any], *, limit: int = 100) -> None:
        encoded = json.dumps(payload, sort_keys=True, default=str)
        list_key = self._key(f"list:{key}")
        client = await self._get_client()
        if client is not None:
            await client.lpush(list_key, encoded)
            await client.ltrim(list_key, 0, max(limit - 1, 0))
            return

        values = self._lists[list_key]
        values.insert(0, encoded)
        del values[limit:]

    async def read_json(self, key: str, *, limit: int = 100) -> list[dict[str, Any]]:
        list_key = self._key(f"list:{key}")
        client = await self._get_client()
        raw_items: list[str]
        if client is not None:
            raw_items = list(await client.lrange(list_key, 0, max(limit - 1, 0)))
        else:
            raw_items = list(self._lists.get(list_key, []))[:limit]
        return [json.loads(item) for item in raw_items]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


runtime_cache = RuntimeCache()