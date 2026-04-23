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

        # The extension posts {page, portal_state: {fields, errors, currentUrl, ...}, pilot_mode}.
        # Tools downstream expect {fields, errors, current_url, page_title, ...} at the top level.
        # Merge the nested snapshot up so either shape works.
        merged = self._flatten_context(context)

        current_url = self._coerce_str(merged.get("current_url") or merged.get("url"))
        page_title = self._coerce_str(merged.get("page_title") or merged.get("title"))
        page_type = self._coerce_str(merged.get("page_type") or context.get("page"))
        focused_field = self._coerce_str(merged.get("focused_field"))

        raw_fields = merged.get("fields")
        fields = raw_fields if isinstance(raw_fields, list) else []
        fields = fields[:_MAX_FIELDS]

        raw_errors = merged.get("errors") or merged.get("validation_errors")
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

    def _flatten_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Accept both the flat `{fields, errors, ...}` shape and the extension's nested
        `{portal_state: {...}}` wrapper, and normalise camelCase extension keys to snake_case.

        Outer context keys take precedence over inner portal_state keys so a caller can override
        any individual field without wrapping the whole payload.
        """
        nested = context.get("portal_state")
        base = dict(nested) if isinstance(nested, dict) else {}
        base.update({key: value for key, value in context.items() if key != "portal_state"})

        alias_map = {
            "currentUrl": "current_url",
            "pageTitle": "page_title",
            "pageType": "page_type",
            "focusedField": "focused_field",
            "openDropdown": "open_dropdown",
            "validationErrors": "errors",
        }
        for src, dst in alias_map.items():
            if src in base and dst not in base:
                base[dst] = base[src]
        return base


portal_context_service = PortalContextService()
