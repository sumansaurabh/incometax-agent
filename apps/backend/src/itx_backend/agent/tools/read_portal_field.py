from __future__ import annotations

from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.portal_context import portal_context_service


def _normalize(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _match(field: dict[str, Any], needle_norm: str, needle_raw: str) -> bool:
    """Match on field id, name, label, or selector. Tolerant to capitalisation and punctuation."""
    for key in ("id", "name", "selector"):
        raw = str(field.get(key) or "")
        if raw and (raw == needle_raw or _normalize(raw) == needle_norm):
            return True
    label = str(field.get("label") or "")
    if label and (label.lower() == needle_raw.lower() or _normalize(label) == needle_norm):
        return True
    return False


@tool_registry.tool(
    name="read_portal_field",
    description=(
        "Read a single field from the latest portal snapshot — far cheaper than "
        "get_portal_context when you only need one value. Supply the field's id, name, label, or "
        "selector; matching is case and punctuation tolerant. Returns the field's current value, "
        "type, required flag, and dropdown options if any. Use this to answer 'what is currently "
        "in the PAN field?' or 'is the regime dropdown filled?' without dumping the whole page."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "field_identifier": {
                "type": "string",
                "description": "id, name, label, or CSS selector of the field to read.",
            },
        },
        "required": ["field_identifier"],
        "additionalProperties": False,
    },
)
async def read_portal_field(
    *,
    thread_id: str,
    field_identifier: str,
) -> dict[str, Any]:
    if not field_identifier or not field_identifier.strip():
        return {"error": "field_identifier_required"}

    snapshot = await portal_context_service.get(thread_id)
    if snapshot is None:
        return {
            "available": False,
            "reason": "no_snapshot_recorded",
            "hint": "The extension has not reported portal state for this thread yet.",
        }

    needle_raw = field_identifier.strip()
    needle_norm = _normalize(needle_raw)

    fields = snapshot.get("fields") or []
    for field in fields:
        if isinstance(field, dict) and _match(field, needle_norm, needle_raw):
            projected: dict[str, Any] = {
                k: field[k]
                for k in ("id", "name", "label", "type", "value", "placeholder", "required", "focused")
                if k in field and field[k] not in (None, "")
            }
            options = field.get("options")
            if isinstance(options, list) and options:
                projected["options"] = [
                    opt if isinstance(opt, (str, int, float))
                    else opt.get("label") or opt.get("value")
                    for opt in options
                    if opt is not None
                ][:50]
            return {"available": True, "field": projected, "captured_at": snapshot.get("captured_at")}

    return {
        "available": False,
        "reason": "field_not_found_in_snapshot",
        "searched_for": field_identifier,
        "visible_field_count": len(fields),
    }
