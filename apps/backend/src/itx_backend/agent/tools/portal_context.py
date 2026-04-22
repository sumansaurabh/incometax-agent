from __future__ import annotations

from typing import Any

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.portal_context import portal_context_service


def _summarize_fields(fields: list[Any]) -> list[dict[str, Any]]:
    """Project the extension's raw field array down to the attributes the LLM actually uses.

    Extensions may stuff bounding boxes, css selectors, ARIA attributes etc. into each field
    record. The LLM only needs enough to describe a field to the user: label, value, required
    flag, options for a dropdown. Anything else wastes input tokens.
    """
    summary: list[dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        entry: dict[str, Any] = {}
        for key in ("id", "name", "label", "type", "value", "placeholder", "required", "focused"):
            if key in field and field[key] not in (None, ""):
                entry[key] = field[key]
        options = field.get("options")
        if isinstance(options, list) and options:
            entry["options"] = [
                opt if isinstance(opt, (str, int, float)) else opt.get("label") or opt.get("value")
                for opt in options
                if opt is not None
            ][:50]
        if entry:
            summary.append(entry)
    return summary


@tool_registry.tool(
    name="get_portal_context",
    description=(
        "Get the current state of the e-Filing portal page the user is looking at: URL, page "
        "title, visible form fields (with their labels, current values, types, and any dropdown "
        "options), the field the user is currently focused on, and any validation errors on the "
        "page. Call this whenever the user refers to the page in front of them — for example "
        "'what should I select in the dropdown?', 'why is the Continue button disabled?', 'which "
        "option applies to me?'. Returns an object with `current_url`, `page_title`, `page_type`, "
        "`focused_field`, `fields` (array), `errors` (array). Returns `{\"available\": false}` if "
        "the extension has not yet reported any page state for this thread."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
async def get_portal_context(*, thread_id: str) -> dict[str, Any]:
    snapshot = await portal_context_service.get(thread_id)
    if snapshot is None:
        return {
            "available": False,
            "reason": "no_snapshot_recorded",
            "hint": (
                "Ask the user to click somewhere on the portal page or refresh the side panel; "
                "the extension pushes the portal state with each chat turn."
            ),
        }
    return {
        "available": True,
        "current_url": snapshot.get("current_url"),
        "page_title": snapshot.get("page_title"),
        "page_type": snapshot.get("page_type"),
        "focused_field": snapshot.get("focused_field"),
        "fields": _summarize_fields(snapshot.get("fields") or []),
        "errors": snapshot.get("errors") or [],
        "captured_at": snapshot.get("captured_at"),
    }
