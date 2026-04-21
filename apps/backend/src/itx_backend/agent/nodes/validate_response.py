from __future__ import annotations

from itx_backend.agent.state import AgentState


async def run(state: AgentState) -> AgentState:
    executed = state.get("executed_actions", [])
    blocked = state.get("blocked_actions", [])

    failed_readback = [
        x
        for x in executed
        if x.get("result") in {"readback_mismatch", "validation_error"}
        or not x.get("read_after_write", {}).get("ok", False)
    ]

    needs_recovery = len(failed_readback) > 0
    selector_failure = None
    if needs_recovery:
        first = failed_readback[0]
        selector_failure = {
            "field_id": first.get("field_id"),
            "field_label": first.get("field_label"),
            "page_type": first.get("page_type", "unknown"),
            "selector": first.get("selector"),
            "error_type": first.get("result", "readback_mismatch"),
        }

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": (
                f"Validation complete: {len(executed)} executed, "
                f"{len(blocked)} blocked, {len(failed_readback)} read-back failures."
            ),
            "metadata": {"node": "validate_response", "needs_recovery": needs_recovery},
        }
    )

    state.apply_update(
        {
            "messages": messages,
            "validation_summary": {
                "executed": len(executed),
                "blocked": len(blocked),
                "readback_failures": len(failed_readback),
            },
            "selector_failure": selector_failure,
        }
    )
    return state
