from __future__ import annotations

import logging
from typing import Any

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.consent import active_purposes
from itx_backend.services.filing_runtime import filing_runtime
from itx_backend.services.viewport_capture import (
    ViewportCaptureError,
    ViewportCaptureTimeout,
    viewport_capture_service,
)

logger = logging.getLogger(__name__)

# Payload the LLM receives on success: a real image content block plus structured metadata.
# The shape matches Anthropic's content-block spec so the runner can pass it through unchanged.
_SCREEN_CAPTURE_CONSENT = "screen_capture"
# Anthropic documents a practical per-image budget around ~3.75 MB decoded. JPEG at quality 70
# on a 1440p viewport lands at ~200-600 KB base64. Anything over 1.5 MB is almost certainly a
# bug; refuse rather than bloat the context window.
_MAX_BYTES = 1_500_000


@tool_registry.tool(
    name="capture_viewport",
    description=(
        "Capture a JPEG screenshot of the visible portion of the user's e-Filing portal tab. "
        "Use ONLY when the DOM snapshot from get_portal_context is insufficient — for example, the "
        "user asks about a chart, a rendered PDF preview, a captcha image, or the visual layout of "
        "a page whose fields the adapter could not read. Do NOT call this for questions about form "
        "fields, dropdowns, text content, or validation errors — get_portal_context already has "
        "those and is far cheaper. The user has a separate 'screen_capture' consent that must be "
        "granted; if it is missing, the tool returns a consent_required error and you must ask the "
        "user for consent rather than retrying. Returns either an `image` content block the model "
        "can see, or a structured error."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "One-sentence justification naming the specific visual element you need to see.",
            },
        },
        "required": ["reason"],
        "additionalProperties": False,
    },
)
async def capture_viewport(*, thread_id: str, reason: str) -> dict[str, Any]:
    if not reason or not reason.strip():
        return {"ok": False, "error": "reason_required"}

    state = await checkpointer.latest(thread_id)
    if state is None:
        return {"ok": False, "error": "thread_not_found"}
    user_id = state.user_id

    consents = await filing_runtime.list_consents(thread_id)
    if _SCREEN_CAPTURE_CONSENT not in active_purposes(consents):
        return {
            "ok": False,
            "error": "consent_required",
            "missing_purpose": _SCREEN_CAPTURE_CONSENT,
            "hint": (
                "The user has not granted the screen_capture consent. Ask them to approve it before "
                "retrying — do not call this tool again until they confirm."
            ),
        }

    if not viewport_capture_service.has_socket(user_id):
        return {
            "ok": False,
            "error": "extension_not_connected",
            "hint": "The browser extension is not currently connected. Ask the user to open the side panel on the portal.",
        }

    try:
        capture = await viewport_capture_service.request_capture(user_id=user_id)
    except ViewportCaptureTimeout:
        return {"ok": False, "error": "capture_timed_out"}
    except ViewportCaptureError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:  # noqa: BLE001 — capture is best-effort, never break the chat turn
        logger.exception("capture_viewport.unexpected_error", extra={"thread_id": thread_id})
        return {"ok": False, "error": "capture_failed"}

    size_bytes = int(capture.get("size_bytes") or 0)
    if size_bytes > _MAX_BYTES:
        return {"ok": False, "error": "capture_too_large", "size_bytes": size_bytes, "limit_bytes": _MAX_BYTES}

    return {
        "ok": True,
        "reason": reason.strip()[:500],
        "image": {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": capture.get("media_type", "image/jpeg"),
                "data": capture["data_base64"],
            },
        },
        "captured_at": capture.get("captured_at"),
        "viewport": capture.get("viewport") or {},
        "size_bytes": size_bytes,
    }
