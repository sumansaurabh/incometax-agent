from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from asyncpg import Record

from itx_backend.agent.runner import run_turn
from itx_backend.db.session import get_pool
from itx_backend.services.portal_context import portal_context_service

logger = logging.getLogger(__name__)

# How many prior messages to feed back to the model. Keep this bounded — the model's system prompt
# + tool schemas are already cached, but raw message history isn't.
_HISTORY_WINDOW = 20


class ChatService:
    async def list_messages(self, thread_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, thread_id, role, content, message_type, metadata::text as metadata, created_at
                from chat_messages
                where thread_id = $1
                order by created_at desc
                limit $2
                """,
                thread_id,
                max(1, min(limit, 100)),
            )
        return [self._serialize(row) for row in reversed(rows)]

    async def handle_message(
        self,
        *,
        thread_id: str,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        history = await self._load_history_for_llm(thread_id=thread_id)

        if context:
            try:
                await portal_context_service.upsert(thread_id=thread_id, context=context)
            except Exception:  # noqa: BLE001 — snapshot persistence must never break chat
                logger.exception("portal_context_upsert_failed", extra={"thread_id": thread_id})

        user_message = await self._create_message(
            thread_id=thread_id,
            role="user",
            content=message,
            message_type="text",
            metadata={"context": context or {}},
        )

        turn = await run_turn(
            thread_id=thread_id,
            user_message=message,
            history=history,
            context=context,
        )
        agent_content = turn.get("content") or "I do not have an answer right now. Please try again."
        tool_calls = turn.get("tool_calls") or []
        proposals = self._extract_proposals(tool_calls)
        # Scrub raw results from the persisted metadata — they can be large and occasionally
        # include chunk text. Keep name/input/is_error for observability.
        scrubbed_tool_calls = [
            {k: v for k, v in call.items() if k != "result"}
            for call in tool_calls
        ]
        metadata: dict[str, Any] = {
            "tool_calls": scrubbed_tool_calls,
            "steps": turn.get("steps", 0),
            "agent": turn.get("metadata") or {},
        }
        if proposals:
            metadata["proposals"] = proposals

        agent_message = await self._create_message(
            thread_id=thread_id,
            role="agent",
            content=agent_content,
            message_type="text",
            metadata=metadata,
        )
        return {
            "thread_id": thread_id,
            "user_message": user_message,
            "agent_message": agent_message,
        }

    def _extract_proposals(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Pick up any propose_fill results so the extension can render a diff card.

        The runner now attaches `result` to each tool call. We filter for successful propose_fill
        calls that yielded a proposal_id — nothing_to_fill or errors are intentionally dropped
        from the chat metadata so the UI does not render empty cards.
        """
        proposals: list[dict[str, Any]] = []
        for call in tool_calls:
            if call.get("name") != "propose_fill" or call.get("is_error"):
                continue
            result = call.get("result") or {}
            if not isinstance(result, dict):
                continue
            proposal_id = result.get("proposal_id")
            if not proposal_id:
                continue
            proposals.append(
                {
                    "proposal_id": proposal_id,
                    "approval_key": result.get("approval_key"),
                    "status": result.get("status"),
                    "sensitivity": result.get("sensitivity"),
                    "expires_at": result.get("expires_at"),
                    "total_actions": result.get("total_actions"),
                    "high_confidence_actions": result.get("high_confidence_actions"),
                    "low_confidence_actions": result.get("low_confidence_actions"),
                    "pages": result.get("pages") or [],
                    "message": result.get("message"),
                }
            )
        return proposals

    async def _load_history_for_llm(self, *, thread_id: str) -> list[dict[str, Any]]:
        """Pull the last N persisted messages and reshape them into Anthropic's format.

        We drop any message whose role we don't understand; we do not try to replay tool calls from
        history (tool_use/tool_result pairs are turn-local). This keeps history simple and durable.
        """
        messages = await self.list_messages(thread_id=thread_id, limit=_HISTORY_WINDOW)
        llm_history: list[dict[str, Any]] = []
        for entry in messages:
            role = entry.get("role")
            content = (entry.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                llm_history.append({"role": "user", "content": content})
            elif role == "agent":
                llm_history.append({"role": "assistant", "content": content})
        return llm_history

    async def _create_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        message_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        pool = await get_pool()
        message_id = uuid.uuid4()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                insert into chat_messages (id, thread_id, role, content, message_type, metadata)
                values ($1, $2, $3, $4, $5, $6::jsonb)
                returning id, thread_id, role, content, message_type, metadata::text as metadata, created_at
                """,
                message_id,
                thread_id,
                role,
                content,
                message_type,
                json.dumps(metadata, sort_keys=True, default=str),
            )
        return self._serialize(row)

    def _serialize(self, row: Record) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "thread_id": row["thread_id"],
            "role": row["role"],
            "content": row["content"],
            "message_type": row["message_type"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"].isoformat(),
        }


chat_service = ChatService()
