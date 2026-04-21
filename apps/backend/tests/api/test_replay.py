from __future__ import annotations

import os
import unittest

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.replay import CaptureSnapshotRequest, ReplayRequest, capture, replay, runs, snapshots
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.auth_runtime import AuthContext


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class ReplayApiTest(unittest.IsolatedAsyncioTestCase):
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
            await connection.execute("truncate table replay_runs, replay_snapshots, agent_checkpoints cascade")

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table replay_runs, replay_snapshots, agent_checkpoints cascade")
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()

    async def test_capture_and_replay_are_persisted(self) -> None:
        self._bind_auth("user-replay")
        await checkpointer.save(
            AgentState(
                thread_id="thread-replay-1",
                user_id="user-replay",
                itr_type="ITR-1",
                current_page="salary-schedule",
            )
        )

        captured = await capture(
            CaptureSnapshotRequest(
                thread_id="thread-replay-1",
                page_type="salary-schedule",
                dom_html="<input id='grossSalary' /><input id='employerName' />",
                url="https://www.incometax.gov.in/salary",
                metadata={"source": "test"},
            )
        )
        self.assertIn("snapshot_id", captured)

        replayed = await replay(
            ReplayRequest(
                snapshot_id=captured["snapshot_id"],
                expected_selectors=["grossSalary", "missingSelector"],
            )
        )
        self.assertFalse(replayed["success"])
        self.assertEqual(replayed["mismatches"][0]["selector"], "missingSelector")

        snapshot_items = await snapshots(thread_id="thread-replay-1")
        run_items = await runs()
        self.assertEqual(len(snapshot_items["items"]), 1)
        self.assertEqual(snapshot_items["items"][0]["thread_id"], "thread-replay-1")
        self.assertEqual(len(run_items["items"]), 1)
        self.assertEqual(run_items["items"][0]["snapshot_id"], captured["snapshot_id"])
        await close_connection_pool()

    async def test_capture_and_replay_are_persisted(self) -> None:
        self._bind_auth("user-replay")
        await checkpointer.save(
            AgentState(
                thread_id="thread-replay-1",
                user_id="user-replay",
                itr_type="ITR-1",
                current_page="salary-schedule",
            )
        )

        captured = await capture(
            CaptureSnapshotRequest(
                thread_id="thread-replay-1",
                page_type="salary-schedule",
                dom_html="<input id='grossSalary' /><input id='employerName' />",
                url="https://www.incometax.gov.in/salary",
                metadata={"source": "test"},
            )
        )
        self.assertIn("snapshot_id", captured)

        replayed = await replay(
            ReplayRequest(
                snapshot_id=captured["snapshot_id"],
                expected_selectors=["grossSalary", "missingSelector"],
            )
        )
        self.assertFalse(replayed["success"])
        self.assertEqual(replayed["mismatches"][0]["selector"], "missingSelector")

        snapshot_items = await snapshots(thread_id="thread-replay-1")
        run_items = await runs()
        self.assertEqual(len(snapshot_items["items"]), 1)
        self.assertEqual(snapshot_items["items"][0]["thread_id"], "thread-replay-1")
        self.assertEqual(len(run_items["items"]), 1)
        self.assertEqual(run_items["items"][0]["snapshot_id"], captured["snapshot_id"])