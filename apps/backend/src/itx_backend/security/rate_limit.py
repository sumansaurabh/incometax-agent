from collections import defaultdict


class FixedWindowRateLimiter:
    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self.counts: dict[str, int] = defaultdict(int)

    def allow(self, key: str) -> bool:
        self.counts[key] += 1
        return self.counts[key] <= self.limit
