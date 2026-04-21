from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Optional

from itx_backend.agent.state import AgentState
from itx_backend.db.session import get_pool


PoolProvider = Callable[[], Awaitable[Any]]

class AsyncPostgresCheckpointer:
    def __init__(self, pool_provider: PoolProvider = get_pool) -> None:
        self._pool_provider = pool_provider

    def _deserialize(self, payload: str) -> AgentState:
        return AgentState.model_validate(json.loads(payload))

    async def save(self, state: AgentState) -> None:
        payload = json.dumps(state.model_dump(mode="json"), sort_keys=True)
        pool = await self._pool_provider()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into agent_checkpoints (thread_id, current_node, state_json)
                values ($1, $2, $3::jsonb)
                """,
                state.thread_id,
                state.current_node,
                payload,
            )

    async def latest(self, thread_id: str) -> Optional[AgentState]:
        pool = await self._pool_provider()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select state_json::text as state_json
                from agent_checkpoints
                where thread_id = $1
                order by id desc
                limit 1
                """,
                thread_id,
            )
        if not row:
            return None
        return self._deserialize(row["state_json"])

    async def list_thread_ids(self) -> list[str]:
        pool = await self._pool_provider()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                "select distinct thread_id from agent_checkpoints order by thread_id"
            )
        return [row["thread_id"] for row in rows]

    async def history(self, thread_id: str) -> list[AgentState]:
        pool = await self._pool_provider()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select state_json::text as state_json
                from agent_checkpoints
                where thread_id = $1
                order by id asc
                """,
                thread_id,
            )
        return [self._deserialize(row["state_json"]) for row in rows]


    async def list_latest_states(self) -> list[AgentState]:
        pool = await self._pool_provider()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select distinct on (thread_id) state_json::text as state_json
                from agent_checkpoints
                order by thread_id, id desc
                """
            )
        return [self._deserialize(row["state_json"]) for row in rows]


checkpointer = AsyncPostgresCheckpointer()
