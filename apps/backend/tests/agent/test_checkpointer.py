import os
import unittest

from itx_backend.agent.checkpointer import AsyncPostgresCheckpointer
from itx_backend.agent.state import AgentState
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class AsyncPostgresCheckpointerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table agent_checkpoints")
        self.checkpointer = AsyncPostgresCheckpointer()

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table agent_checkpoints")
        await close_connection_pool()

    async def test_persists_history_across_instances(self) -> None:
        first = AgentState(thread_id="thread-1", user_id="user-1")
        first.messages.append({"role": "assistant", "content": "first"})
        await self.checkpointer.save(first)

        second = first.model_copy(deep=True)
        second.current_node = "archive"
        second.archived = True
        second.messages.append({"role": "assistant", "content": "second"})
        await self.checkpointer.save(second)

        latest = await self.checkpointer.latest("thread-1")
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertTrue(latest.archived)
        self.assertEqual(len(latest.messages), 2)

        reopened = AsyncPostgresCheckpointer()
        history = await reopened.history("thread-1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].messages[0]["content"], "first")
        self.assertEqual(history[1].current_node, "archive")
        self.assertEqual(await reopened.list_thread_ids(), ["thread-1"])

    async def test_returns_empty_results_for_unknown_thread(self) -> None:
        self.assertIsNone(await self.checkpointer.latest("missing"))
        self.assertEqual(await self.checkpointer.history("missing"), [])
        self.assertEqual(await self.checkpointer.list_thread_ids(), [])