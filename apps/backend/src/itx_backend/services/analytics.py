from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Optional

from itx_backend.db.session import get_pool
from itx_backend.services.portal_drift_autopilot import portal_drift_autopilot
from itx_backend.services.replay_harness import replay_harness
from itx_backend.services.startup_health import startup_health_service
from itx_backend.telemetry.agent_observability import agent_observability
from itx_backend.telemetry.drift import get_drift_telemetry
from itx_backend.telemetry.metrics import metrics
from itx_backend.telemetry.tracing import get_trace_status


@dataclass
class FilingEvent:
    event_type: str
    stage: str
    thread_id: str
    payload: dict[str, Any]
    ts: str


class AnalyticsService:
    async def track(self, event_type: str, stage: str, thread_id: str, payload: Optional[dict[str, Any]] = None) -> None:
        ts_dt = datetime.now(timezone.utc)
        event = FilingEvent(
            event_type=event_type,
            stage=stage,
            thread_id=thread_id,
            payload=payload or {},
            ts=ts_dt.isoformat(),
        )
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into analytics_events (event_type, stage, thread_id, payload, ts)
                values ($1, $2, $3, $4::jsonb, $5)
                """,
                event.event_type,
                event.stage,
                event.thread_id,
                json.dumps(event.payload, sort_keys=True),
                ts_dt,
            )
        metrics.inc(f"analytics.{event_type}")

    async def dashboard(self) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            totals = await connection.fetchrow(
                """
                select count(*) as events, count(distinct thread_id) as unique_threads
                from analytics_events
                """
            )
            by_stage_rows = await connection.fetch(
                """
                select stage, count(*) as count
                from analytics_events
                group by stage
                order by stage asc
                """
            )
            by_type_rows = await connection.fetch(
                """
                select event_type, count(*) as count
                from analytics_events
                group by event_type
                order by event_type asc
                """
            )
            recent_rows = await connection.fetch(
                """
                select to_char(ts::date, 'YYYY-MM-DD') as bucket, count(*) as count
                from analytics_events
                where ts >= now() - interval '14 days'
                group by ts::date
                order by bucket asc
                """
            )
        drift_stats = get_drift_telemetry().get_statistics()
        drift_recommendations = portal_drift_autopilot.run(get_drift_telemetry().export_for_training())
        return {
            "totals": {
                "events": int(totals["events"] if totals else 0),
                "unique_threads": int(totals["unique_threads"] if totals else 0),
            },
            "by_stage": {row["stage"]: int(row["count"]) for row in by_stage_rows},
            "by_type": {row["event_type"]: int(row["count"]) for row in by_type_rows},
            "daily_activity": {row["bucket"]: int(row["count"]) for row in recent_rows},
            "metrics": metrics.snapshot(),
            "operations": {
                "replay": await replay_harness.dashboard(),
                "drift": drift_stats,
                "drift_recommendations": drift_recommendations,
                "agent_observability": await agent_observability.summary(),
                "runtime_health": startup_health_service.latest(),
                "tracing": get_trace_status(),
            },
        }

    async def timeline(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select event_type, stage, payload::text as payload, ts
                from analytics_events
                where thread_id = $1
                order by ts asc, id asc
                """,
                thread_id,
            )
        return [
            {
                "event_type": row["event_type"],
                "stage": row["stage"],
                "ts": row["ts"].isoformat() if row["ts"] else datetime.now(timezone.utc).isoformat(),
                "payload": json.loads(row["payload"] or "{}"),
            }
            for row in rows
        ]

    async def purge_thread(self, thread_id: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("delete from analytics_events where thread_id = $1", thread_id)

    async def agent_events(self, *, thread_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        return await agent_observability.recent_events(thread_id=thread_id, limit=limit)


analytics_service = AnalyticsService()
