import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from itx_backend.agent.checkpointer import SQLiteCheckpointer
from itx_backend.api.threads import ThreadStartRequest, get_thread, get_thread_history, start_thread


class ThreadsApiTest(unittest.TestCase):
    def test_start_thread_writes_checkpoint_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            checkpointer = SQLiteCheckpointer(Path(tmp_dir) / "checkpoints.sqlite3")

            with patch("itx_backend.agent.graph.checkpointer", checkpointer), patch(
                "itx_backend.api.threads.checkpointer", checkpointer
            ):
                final_state = start_thread(ThreadStartRequest(user_id="user-42"))
                latest_state = get_thread(final_state.thread_id)
                history = get_thread_history(final_state.thread_id)

        self.assertTrue(final_state.archived)
        self.assertFalse(isinstance(latest_state, dict) and latest_state.get("error"))
        self.assertEqual(history["thread_id"], final_state.thread_id)
        self.assertGreater(len(history["checkpoints"]), 3)
        self.assertTrue(history["checkpoints"][-1]["archived"])