from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional
import hashlib

from itx_backend.services.runtime_cache import runtime_cache
from itx_backend.telemetry.metrics import metrics


@dataclass
class AgentNodeEvent:
    event_id: str
    thread_id: str
    node_name: str
    status: str
    timestamp: str
    duration_ms: Optional[int]
    current_page: Optional[str]
    metadata: dict[str, Any]


class AgentObservabilityService:
    def __init__(self) -> None:
        self._events: list[AgentNodeEvent] = []

    def _event_id(self, *, thread_id: str, node_name: str, status: str, timestamp: str) -> str:
        digest = hashlib.sha256(f"{thread_id}:{node_name}:{status}:{timestamp}".encode("utf-8")).hexdigest()
        return digest[:20]

    async def record(
        self,
        *,
        thread_id: str,
        node_name: str,
        status: str,
        duration_ms: Optional[int] = None,
        current_page: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        event = AgentNodeEvent(
            event_id=self._event_id(
                thread_id=thread_id,
                node_name=node_name,
                status=status,
                timestamp=timestamp,
            ),
            thread_id=thread_id,
            node_name=node_name,
            status=status,
            timestamp=timestamp,
            duration_ms=duration_ms,
            current_page=current_page,
            metadata=metadata or {},
        )
        self._events.insert(0, event)
        del self._events[200:]
        payload = asdict(event)
        await runtime_cache.append_json("agent-events", payload, limit=200)
        await runtime_cache.append_json(f"agent-events:{thread_id}", payload, limit=100)
        metrics.inc(f"agent.{node_name}.{status}")
        return payload

    async def recent_events(self, *, thread_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        cache_key = "agent-events" if thread_id is None else f"agent-events:{thread_id}"
        cached = await runtime_cache.read_json(cache_key, limit=limit)
        if cached:
            return cached
        if thread_id is None:
            return [asdict(event) for event in self._events[:limit]]
        return [asdict(event) for event in self._events if event.thread_id == thread_id][:limit]

    async def summary(self) -> dict[str, Any]:
        events = await self.recent_events(limit=200)
        by_status: dict[str, int] = {}
        by_node: dict[str, int] = {}
        durations: list[int] = []
        for event in events:
            status = str(event.get("status") or "unknown")
            node_name = str(event.get("node_name") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            by_node[node_name] = by_node.get(node_name, 0) + 1
            duration_ms = event.get("duration_ms")
            if isinstance(duration_ms, int):
                durations.append(duration_ms)
        average_duration_ms = round(sum(durations) / len(durations), 2) if durations else 0.0
        return {
            "backend": runtime_cache.backend(),
            "total_events": len(events),
            "by_status": by_status,
            "by_node": by_node,
            "average_duration_ms": average_duration_ms,
            "recent_failures": [event for event in events if event.get("status") == "failed"][:5],
        }


agent_observability = AgentObservabilityService()