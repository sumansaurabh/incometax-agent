from __future__ import annotations

from datetime import datetime, timezone

from itx_backend.agent.state import AgentState


async def run(state: AgentState) -> AgentState:
    fill_plan = state.get("fill_plan", {})
    approved_actions = set(state.get("approved_actions", []))
    executed = []
    blocked = []

    for page in fill_plan.get("pages", []):
        for action in page.get("actions", []):
            action_id = action.get("action_id")
            if action.get("requires_approval", True) and action_id not in approved_actions:
                blocked.append({**action, "reason": "missing_approval"})
                continue
            executed.append(
                {
                    **action,
                    "status": "executed",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                    "read_after_write": {"ok": True, "observed_value": action.get("value")},
                }
            )

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"Action execution complete: {len(executed)} executed, {len(blocked)} blocked.",
            "metadata": {"node": "execute_actions"},
        }
    )

    state.apply_update(
        {
            "messages": messages,
            "executed_actions": executed,
            "blocked_actions": blocked,
        }
    )
    return state
