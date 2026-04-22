from collections import defaultdict
import time

from itx_backend.services.runtime_cache import runtime_cache


class FixedWindowRateLimiter:
    def __init__(self, limit: int = 100, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.counts: dict[str, int] = defaultdict(int)
        self.current_window = int(time.time() // max(self.window_seconds, 1))

    async def allow(self, key: str) -> bool:
        if runtime_cache.backend() == "redis":
            count = await runtime_cache.increment_window(f"ratelimit:{key}", self.window_seconds)
            return count <= self.limit

        next_window = int(time.time() // max(self.window_seconds, 1))
        if next_window != self.current_window:
            self.counts.clear()
            self.current_window = next_window
        self.counts[key] += 1
        return self.counts[key] <= self.limit
