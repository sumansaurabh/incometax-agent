from collections import Counter


class MetricsRegistry:
    def __init__(self) -> None:
        self._counter = Counter()

    def inc(self, key: str) -> None:
        self._counter[key] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counter)


metrics = MetricsRegistry()
