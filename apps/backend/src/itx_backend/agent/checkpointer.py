from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from itx_backend.agent.state import AgentState
from itx_backend.config import settings


class SQLiteCheckpointer:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists agent_checkpoints (
                    id integer primary key autoincrement,
                    thread_id text not null,
                    current_node text not null,
                    state_json text not null,
                    created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                )
                """
            )
            connection.execute(
                "create index if not exists idx_agent_checkpoints_thread_id on agent_checkpoints(thread_id, id)"
            )

    def _deserialize(self, payload: str) -> AgentState:
        return AgentState.model_validate(json.loads(payload))

    def save(self, state: AgentState) -> None:
        payload = json.dumps(state.model_dump(mode="json"), sort_keys=True)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                insert into agent_checkpoints (thread_id, current_node, state_json)
                values (?, ?, ?)
                """,
                (state.thread_id, state.current_node, payload),
            )

    def latest(self, thread_id: str) -> AgentState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select state_json
                from agent_checkpoints
                where thread_id = ?
                order by id desc
                limit 1
                """,
                (thread_id,),
            ).fetchone()
        if not row:
            return None
        return self._deserialize(row["state_json"])

    def list_thread_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "select distinct thread_id from agent_checkpoints order by thread_id"
            ).fetchall()
        return [row["thread_id"] for row in rows]

    def history(self, thread_id: str) -> list[AgentState]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select state_json
                from agent_checkpoints
                where thread_id = ?
                order by id asc
                """,
                (thread_id,),
            ).fetchall()
        return [self._deserialize(row["state_json"]) for row in rows]


checkpointer = SQLiteCheckpointer(settings.checkpoint_db_path)
