from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState


def current_quarantine_status(state: AgentState) -> dict[str, Any]:
    status = state.get("security_status", {}) or {}
    return {
        "quarantined": bool(status.get("quarantined", False)),
        "reason": status.get("reason"),
        "requested_by": status.get("requested_by"),
        "details": status.get("details", {}),
        "quarantined_at": status.get("quarantined_at"),
        "resumed_at": status.get("resumed_at"),
        "resumed_by": status.get("resumed_by"),
        "resume_note": status.get("resume_note"),
    }


def ensure_thread_not_quarantined(state: AgentState, action: str) -> None:
    status = current_quarantine_status(state)
    if status.get("quarantined"):
        raise HTTPException(status_code=423, detail=f"thread_quarantined:{action}")


async def quarantine_thread(thread_id: str, *, requested_by: str, reason: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    state = await checkpointer.latest(thread_id)
    if state is None:
        raise KeyError(thread_id)

    now = datetime.now(timezone.utc).isoformat()
    status = current_quarantine_status(state)
    status.update(
        {
            "quarantined": True,
            "reason": reason,
            "requested_by": requested_by,
            "details": details or {},
            "quarantined_at": status.get("quarantined_at") or now,
            "resumed_at": None,
            "resumed_by": None,
            "resume_note": None,
        }
    )
    state.apply_update({"security_status": status})
    await checkpointer.save(state)
    return status


async def resume_thread(thread_id: str, *, requested_by: str, note: str | None = None) -> dict[str, Any]:
    state = await checkpointer.latest(thread_id)
    if state is None:
        raise KeyError(thread_id)

    status = current_quarantine_status(state)
    status.update(
        {
            "quarantined": False,
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "resumed_by": requested_by,
            "resume_note": note,
        }
    )
    state.apply_update({"security_status": status})
    await checkpointer.save(state)
    return status