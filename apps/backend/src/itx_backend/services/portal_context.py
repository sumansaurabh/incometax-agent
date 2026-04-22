from __future__ import annotations

import json
import logging
from typing import Any, Optional

from itx_backend.db.session import get_pool

logger = logging.getLogger(__name__)

# Maximum size of each stored JSON field. Portal states can be surprisingly large (hundreds of
# fields on some pages); clipping keeps DB rows sane and the LLM context bounded.
_MAX_FIELDS = 200
_MAX_ERRORS = 50
_MAX_RAW_CHARS = 32_000


class PortalContextService:
    """Per-thread store of the most recent portal snapshot captured by the browser extension.

    Only the latest snapshot is kept (the table is keyed by thread_id). History is available via
    the `action_runtime` table's `portal_state_before` / `portal_state_after` columns for auditing.
    """

    async def upsert(self, *, thread_id: str, context: dict[str, Any]) -> None:
        if not thread_id or not isinstance(context, dict):
            return

        current_url = self._coerce_str(context.get("current_url") or context.get("url"))
        page_title = self._coerce_str(context.get("page_title") or context.get("title"))
        page_type = self._coerce_str(context.get("page_type"))
        focused_field = self._coerce_str(context.get("focused_field"))

        raw_fields = context.get("fields")
        fields = raw_fields if isinstance(raw_fields, list) else []
        fields = fields[:_MAX_FIELDS]

        raw_errors = context.get("errors")
        errors = raw_errors if isinstance(raw_errors, list) else []
        errors = errors[:_MAX_ERRORS]

        raw_payload = json.dumps(context, default=str, sort_keys=True)
        if len(raw_payload) > _MAX_RAW_CHARS:
            raw_payload = raw_payload[:_MAX_RAW_CHARS]

        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into portal_snapshots (
                    thread_id, current_url, page_title, page_type, focused_field,
                    fields, errors, raw, captured_at, updated_at
                )
                values ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, now(), now())
                on conflict (thread_id) do update set
                    current_url = excluded.current_url,
                    page_title = excluded.page_title,
                    page_type = excluded.page_type,
                    focused_field = excluded.focused_field,
                    fields = excluded.fields,
                    errors = excluded.errors,
                    raw = excluded.raw,
                    updated_at = now()
                """,
                thread_id,
                current_url,
                page_title,
                page_type,
                focused_field,
                json.dumps(fields, default=str),
                json.dumps(errors, default=str),
                raw_payload,
            )

    async def get(self, thread_id: str) -> Optional[dict[str, Any]]:
        if not thread_id:
            return None
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select thread_id, current_url, page_title, page_type, focused_field,
                       fields::text as fields, errors::text as errors, raw::text as raw,
                       captured_at, updated_at
                from portal_snapshots
                where thread_id = $1
                """,
                thread_id,
            )
        if row is None:
            return None
        return {
            "thread_id": row["thread_id"],
            "current_url": row["current_url"],
            "page_title": row["page_title"],
            "page_type": row["page_type"],
            "focused_field": row["focused_field"],
            "fields": json.loads(row["fields"]) if row["fields"] else [],
            "errors": json.loads(row["errors"]) if row["errors"] else [],
            "raw": json.loads(row["raw"]) if row["raw"] else {},
            "captured_at": row["captured_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    def _coerce_str(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:1024]


portal_context_service = PortalContextService()
