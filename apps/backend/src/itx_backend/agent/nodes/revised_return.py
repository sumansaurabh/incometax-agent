"""
Revised-return support — Phase 4 requirement.

Allows branching from a previously filed return into a revision thread,
while preserving prior-return context and audit lineage.
"""

from datetime import datetime, timezone
from typing import Any
import hashlib

from ..state import AgentState


def _new_revision_thread_id(base_thread_id: str, revision_number: int) -> str:
    raw = f"{base_thread_id}:rev:{revision_number}:{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


async def revised_return(state: AgentState) -> dict[str, Any]:
    revision_request = state.get("revision_request")
    if not revision_request:
        return {
            "messages": state.get("messages", []),
            "revision_status": "not_requested",
        }

    prior_return = revision_request.get("prior_return", {})
    if not prior_return:
        messages = state.get("messages", [])
        messages.append({
            "role": "assistant",
            "content": "Revision requested but prior return context is missing.",
            "metadata": {"node": "revised_return", "error": True},
        })
        return {"messages": messages, "revision_status": "missing_prior_return"}

    revision_number = int(revision_request.get("revision_number", 1))
    revision_reason = revision_request.get("reason", "User requested revision")
    base_thread_id = state.thread_id
    revision_thread_id = _new_revision_thread_id(base_thread_id, revision_number)

    # Carry forward previous facts as baseline, user can override during new run.
    merged_tax_facts = dict(prior_return.get("tax_facts", {}))
    merged_tax_facts.update(state.get("tax_facts", {}))

    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": (
            f"Revised return branch created.\n"
            f"Original Thread: {base_thread_id}\n"
            f"Revision Thread: {revision_thread_id}\n"
            f"Revision Number: {revision_number}\n"
            f"Reason: {revision_reason}"
        ),
        "metadata": {
            "node": "revised_return",
            "revision_thread_id": revision_thread_id,
            "base_thread_id": base_thread_id,
        },
    })

    return {
        "messages": messages,
        "revision_status": "branched",
        "base_thread_id": base_thread_id,
        "thread_id": revision_thread_id,
        "tax_facts": merged_tax_facts,
        "revision_context": {
            "base_thread_id": base_thread_id,
            "revision_number": revision_number,
            "reason": revision_reason,
            "branched_at": datetime.now(timezone.utc).isoformat(),
        },
        "revision_request": None,
    }


def run(state: AgentState) -> AgentState:
    import asyncio

    updates = asyncio.run(revised_return(state))
    state.apply_update(updates)
    return state
