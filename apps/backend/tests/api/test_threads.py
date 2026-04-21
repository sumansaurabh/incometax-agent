import os
import unittest

from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.api.threads import ThreadStartRequest, get_thread, get_thread_history, start_thread
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.auth_runtime import AuthContext


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class ThreadsApiTest(unittest.IsolatedAsyncioTestCase):
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
            await connection.execute("truncate table agent_checkpoints")

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table agent_checkpoints")
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()

    async def test_start_thread_writes_checkpoint_history(self) -> None:
        final_state = await start_thread(ThreadStartRequest(user_id="user-42"))
        self._bind_auth("user-42")
        latest_state = await get_thread(final_state.thread_id)
        history = await get_thread_history(final_state.thread_id)

        self.assertTrue(final_state.archived)
        self.assertFalse(isinstance(latest_state, dict) and latest_state.get("error"))
        self.assertEqual(history["thread_id"], final_state.thread_id)
        self.assertGreater(len(history["checkpoints"]), 3)
        self.assertTrue(history["checkpoints"][-1]["archived"])