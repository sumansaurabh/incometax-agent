from __future__ import annotations

from typing import Any

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.portal_context import portal_context_service


_MAX_HEADINGS = 6
_MAX_DROPDOWN_OPTIONS = 50
_MAX_FIELDS = 60


def _summarize_fields(fields: list[Any]) -> list[dict[str, Any]]:
    """Project the extension's raw field array down to the attributes the LLM actually uses.

    Extensions may stuff bounding boxes, css selectors, ARIA attributes etc. into each field
    record. The LLM only needs enough to describe a field to the user: label, value, required
    flag, options for a dropdown. Anything else wastes input tokens.
    """
    summary: list[dict[str, Any]] = []
    for field in fields:
        if len(summary) >= _MAX_FIELDS:
            break
        if not isinstance(field, dict):
            continue
        entry: dict[str, Any] = {}
        # Adapter fields come in under different names than runtime fields. Accept both.
        label = field.get("label")
        if label:
            entry["label"] = label
        value = field.get("value")
        if value not in (None, ""):
            entry["value"] = value
        for key in ("id", "name", "type", "placeholder", "required", "focused", "key", "selectorHint"):
            if key in field and field[key] not in (None, ""):
                entry[key] = field[key]
        options = field.get("options")
        if isinstance(options, list) and options:
            entry["options"] = [
                opt if isinstance(opt, (str, int, float)) else opt.get("label") or opt.get("value")
                for opt in options
                if opt is not None
            ][:_MAX_DROPDOWN_OPTIONS]
        if entry:
            summary.append(entry)
    return summary


def _summarize_focused_field(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        return {"selector": raw}
    if not isinstance(raw, dict):
        return None
    keep = ("selector", "tag", "label", "value", "role", "ariaExpanded", "aria_expanded")
    out = {k: raw[k] for k in keep if k in raw and raw[k] not in (None, "")}
    return out or None


def _summarize_open_dropdown(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    options_raw = raw.get("options")
    if not isinstance(options_raw, list):
        return None
    options: list[dict[str, Any]] = []
    for opt in options_raw[:_MAX_DROPDOWN_OPTIONS]:
        if isinstance(opt, dict):
            label = opt.get("label") or opt.get("value")
            if not label:
                continue
            options.append(
                {
                    "label": str(label),
                    "value": opt.get("value"),
                    "selected": bool(opt.get("selected")),
                }
            )
        elif isinstance(opt, (str, int, float)):
            options.append({"label": str(opt), "value": None, "selected": False})
    if not options:
        return None
    result: dict[str, Any] = {"options": options}
    if raw.get("label"):
        result["label"] = raw.get("label")
    if raw.get("triggerSelector") or raw.get("trigger_selector"):
        result["trigger_selector"] = raw.get("triggerSelector") or raw.get("trigger_selector")
    return result


def _headings_from_raw(raw: Any) -> list[str]:
    candidate = raw.get("headings") if isinstance(raw, dict) else None
    if not isinstance(candidate, list):
        return []
    return [str(item).strip()[:200] for item in candidate if isinstance(item, (str, int, float))][:_MAX_HEADINGS]


@tool_registry.tool(
    name="get_portal_context",
    description=(
        "Get the current state of the e-Filing portal page the user is looking at: URL, page "
        "title, detected adapter or fallback key, visible form fields (with labels, values, types, "
        "dropdown options), the focused field, the currently open dropdown and its options, page "
        "headings, and any validation errors. Call this whenever the user refers to the page in "
        "front of them — for example 'what should I select in the dropdown?', 'why is Continue "
        "disabled?', 'which option applies to me?'. This is ALMOST ALWAYS the tool you want — "
        "reserve capture_viewport for questions about images, charts, or visual layout the DOM "
        "cannot express. Returns `{available: true, ...}` with the fields above when the "
        "extension has reported any state (even a fallback heading snapshot is useful), or "
        "`{available: false}` only when the extension has sent nothing at all for this thread."
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
    raw = snapshot.get("raw") or {}
    # Pull focus + dropdown from either the top-level snapshot or the nested portalState/raw.
    focused_raw = (
        snapshot.get("focused_field")
        or raw.get("focused_field")
        or raw.get("focusedField")
        or (raw.get("portal_state") or raw.get("portalState") or {}).get("focusedField")
        or (raw.get("portal_state") or raw.get("portalState") or {}).get("focused_field")
    )
    dropdown_raw = (
        raw.get("open_dropdown")
        or raw.get("openDropdown")
        or (raw.get("portal_state") or raw.get("portalState") or {}).get("openDropdown")
        or (raw.get("portal_state") or raw.get("portalState") or {}).get("open_dropdown")
    )
    headings = _headings_from_raw(raw)
    fields = _summarize_fields(snapshot.get("fields") or [])
    errors = snapshot.get("errors") or []
    page_type = snapshot.get("page_type") or "unknown"

    # Don't shortcut to available:false just because page_type is unknown — the fallback
    # detector still gives us headings + fields, which is plenty to reason about.
    return {
        "available": True,
        "current_url": snapshot.get("current_url"),
        "page_title": snapshot.get("page_title"),
        "page_type": page_type,
        "route": raw.get("route"),
        "headings": headings,
        "focused_field": _summarize_focused_field(focused_raw),
        "open_dropdown": _summarize_open_dropdown(dropdown_raw),
        "fields": fields,
        "errors": errors,
        "captured_at": snapshot.get("captured_at"),
    }
