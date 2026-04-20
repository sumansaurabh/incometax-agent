from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from itx_backend.telemetry.metrics import metrics


@dataclass
class FilingEvent:
    event_type: str
    stage: str
    thread_id: str
    payload: dict[str, Any]
    ts: str


class AnalyticsService:
    def __init__(self) -> None:
        self._events: list[FilingEvent] = []

    def track(self, event_type: str, stage: str, thread_id: str, payload: dict[str, Any] | None = None) -> None:
        self._events.append(
            FilingEvent(
                event_type=event_type,
                stage=stage,
                thread_id=thread_id,
                payload=payload or {},
                ts=datetime.now(timezone.utc).isoformat(),
            )
        )
        metrics.inc(f"analytics.{event_type}")

    def dashboard(self) -> dict[str, Any]:
        stage_counts = Counter(e.stage for e in self._events)
        type_counts = Counter(e.event_type for e in self._events)
        return {
            "totals": {
                "events": len(self._events),
                "unique_threads": len({e.thread_id for e in self._events}),
            },
            "by_stage": dict(stage_counts),
            "by_type": dict(type_counts),
            "metrics": metrics.snapshot(),
        }

    def timeline(self, thread_id: str) -> list[dict[str, Any]]:
        return [
            {
                "event_type": e.event_type,
                "stage": e.stage,
                "ts": e.ts,
                "payload": e.payload,
            }
            for e in self._events
            if e.thread_id == thread_id
        ]


analytics_service = AnalyticsService()
