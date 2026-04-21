from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Anomaly:
    key: str
    reason: str
    severity: str
    ts: str
    metadata: dict[str, Any]


class ToolCallAnomalyDetector:
    """
    Lightweight anomaly detector for suspicious tool-call behavior.
    """

    def __init__(self, burst_limit: int = 100, window_size: int = 300) -> None:
        self.burst_limit = burst_limit
        self.window_size = window_size
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._anomalies: list[Anomaly] = []

    def observe(self, key: str, action: str, ts: Optional[float] = None) -> list[Anomaly]:
        import time

        now = ts if ts is not None else time.time()
        q = self._events[key]
        q.append(now)

        while q and (now - q[0]) > self.window_size:
            q.popleft()

        found: list[Anomaly] = []
        if len(q) > self.burst_limit:
            found.append(
                Anomaly(
                    key=key,
                    reason="burst_limit_exceeded",
                    severity="high",
                    ts=datetime.now(timezone.utc).isoformat(),
                    metadata={"count": len(q), "window_seconds": self.window_size, "action": action},
                )
            )

        if action.lower() in {"submit", "everify", "finalize"} and len(q) > max(20, self.burst_limit // 2):
            found.append(
                Anomaly(
                    key=key,
                    reason="high_risk_action_under_high_frequency",
                    severity="critical",
                    ts=datetime.now(timezone.utc).isoformat(),
                    metadata={"count": len(q), "action": action},
                )
            )

        self._anomalies.extend(found)
        return found

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        items = self._anomalies[-limit:]
        return [
            {
                "key": a.key,
                "reason": a.reason,
                "severity": a.severity,
                "ts": a.ts,
                "metadata": a.metadata,
            }
            for a in items
        ]


anomaly_detector = ToolCallAnomalyDetector()
