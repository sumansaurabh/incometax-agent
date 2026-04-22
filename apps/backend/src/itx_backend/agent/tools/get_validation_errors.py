from __future__ import annotations

import logging
from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.db.session import get_pool

logger = logging.getLogger(__name__)


@tool_registry.tool(
    name="get_validation_errors",
    description=(
        "Fetch recent portal validation errors for the current thread — the inline error messages "
        "the e-Filing portal shows when a field is rejected (wrong format, exceeds limit, "
        "required and missing, etc.). Call this when the user asks 'why did the portal reject "
        "this?', 'why is the Continue button disabled?', or 'what's wrong with my entry?'. "
        "Results include the field, the portal's message, and a parsed_reason machine label. If "
        "the portal snapshot also carries live errors, prefer those via get_portal_context; this "
        "tool returns persisted history (post-execution) from the database."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
                "description": "Maximum number of recent errors to return.",
            },
            "page_key": {
                "type": "string",
                "description": "Optional filter to narrow to a specific portal page key.",
            },
        },
        "additionalProperties": False,
    },
)
async def get_validation_errors(
    *,
    thread_id: str,
    limit: int = 10,
    page_key: Optional[str] = None,
) -> dict[str, Any]:
    capped = max(1, min(int(limit), 50))
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            select execution_id::text as execution_id, page_key, field, message, parsed_reason, captured_at
            from validation_errors
            where thread_id = $1
              and ($2::text is null or page_key = $2)
            order by captured_at desc
            limit $3
            """,
            thread_id,
            page_key,
            capped,
        )

    return {
        "thread_id": thread_id,
        "count": len(rows),
        "errors": [
            {
                "execution_id": row["execution_id"],
                "page_key": row["page_key"],
                "field": row["field"],
                "message": row["message"],
                "parsed_reason": row["parsed_reason"],
                "captured_at": row["captured_at"].isoformat() if row["captured_at"] else None,
            }
            for row in rows
        ],
    }
