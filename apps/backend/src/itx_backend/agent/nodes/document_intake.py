from __future__ import annotations

from datetime import datetime, timezone

from itx_backend.agent.state import AgentState


async def run(state: AgentState) -> AgentState:
    docs = state.get("documents", [])
    accepted = []
    rejected = []

    for doc in docs:
        security = doc.get("security", {})
        if security.get("prompt_injection_risk") == "high":
            rejected.append({**doc, "reason": "prompt_injection_risk"})
            continue
        if not doc.get("sanitized", True):
            rejected.append({**doc, "reason": "not_sanitized"})
            continue
        if doc.get("virus_scan", "clean") != "clean":
            rejected.append({**doc, "reason": "virus_scan_failed"})
            continue
        accepted.append({**doc, "accepted_at": datetime.now(timezone.utc).isoformat()})

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"Document intake complete: {len(accepted)} accepted, {len(rejected)} rejected.",
            "metadata": {"node": "document_intake"},
        }
    )

    state.apply_update(
        {
            "messages": messages,
            "documents": accepted,
            "rejected_documents": rejected,
        }
    )
    return state
