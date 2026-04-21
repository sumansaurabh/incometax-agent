import tempfile
import unittest
from pathlib import Path

from itx_backend.agent.checkpointer import SQLiteCheckpointer
from itx_backend.agent.state import AgentState


class SQLiteCheckpointerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "checkpoints.sqlite3"
        self.checkpointer = SQLiteCheckpointer(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_persists_history_across_instances(self) -> None:
        first = AgentState(thread_id="thread-1", user_id="user-1")
        first.messages.append({"role": "assistant", "content": "first"})
        self.checkpointer.save(first)

        second = first.model_copy(deep=True)
        second.current_node = "archive"
        second.archived = True
        second.messages.append({"role": "assistant", "content": "second"})
        self.checkpointer.save(second)

        latest = self.checkpointer.latest("thread-1")
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertTrue(latest.archived)
        self.assertEqual(len(latest.messages), 2)

        reopened = SQLiteCheckpointer(self.db_path)
        history = reopened.history("thread-1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].messages[0]["content"], "first")
        self.assertEqual(history[1].current_node, "archive")
        self.assertEqual(reopened.list_thread_ids(), ["thread-1"])

    def test_returns_empty_results_for_unknown_thread(self) -> None:
        self.assertIsNone(self.checkpointer.latest("missing"))
        self.assertEqual(self.checkpointer.history("missing"), [])
        self.assertEqual(self.checkpointer.list_thread_ids(), [])