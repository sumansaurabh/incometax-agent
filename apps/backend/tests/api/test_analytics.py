from __future__ import annotations

import os
import unittest

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.analytics import TrackEventRequest, dashboard, timeline, track
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.auth_runtime import AuthContext


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class AnalyticsApiTest(unittest.IsolatedAsyncioTestCase):
    def _bind_auth(self, user_id: str) -> None:
        if hasattr(self, "_auth_token") and self._auth_token is not None:
            reset_request_auth(self._auth_token)
        self._auth_token = set_request_auth(
            AuthContext(
                user_id=user_id,
                email=f"{user_id}@example.com",
                device_id=f"device-{user_id}",
                session_id=f"session-{user_id}",
            )
        )

    async def asyncSetUp(self) -> None:
        self._auth_token = None
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table analytics_events, agent_checkpoints cascade")

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table analytics_events, agent_checkpoints cascade")
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()

    async def test_track_dashboard_and_timeline_are_persisted(self) -> None:
        self._bind_auth("user-analytics")
        await checkpointer.save(
            AgentState(
                thread_id="thread-analytics-1",
                user_id="user-analytics",
                itr_type="ITR-1",
            )
        )

        await track(
            TrackEventRequest(
                event_type="thread_started",
                stage="bootstrap",
                thread_id="thread-analytics-1",
                payload={"source": "test"},
            )
        )
        await track(
            TrackEventRequest(
                event_type="summary_generated",
                stage="submission",
                thread_id="thread-analytics-1",
                payload={"version": 1},
            )
        )

        timeline_items = await timeline("thread-analytics-1")
        dashboard_items = await dashboard()

        self.assertEqual(len(timeline_items["items"]), 2)
        self.assertEqual(timeline_items["items"][0]["event_type"], "thread_started")
        self.assertEqual(dashboard_items["totals"]["events"], 2)
        self.assertEqual(dashboard_items["totals"]["unique_threads"], 1)
        self.assertEqual(dashboard_items["by_stage"]["bootstrap"], 1)
        self.assertEqual(dashboard_items["by_stage"]["submission"], 1)
        self.assertEqual(dashboard_items["by_type"]["summary_generated"], 1)