from __future__ import annotations

from itx_backend.agent.state import AgentState


def _severity(diff_ratio: float) -> str:
    if diff_ratio < 0.03:
        return "harmless"
    if diff_ratio < 0.08:
        return "prefill_issue"
    if diff_ratio < 0.15:
        return "missing-doc"
    return "under-reporting"


async def run(state: AgentState) -> AgentState:
    tax_facts = state.get("tax_facts", {})
    ais = state.get("ais_facts", {})

    mismatches = []
    for key, ais_val in ais.items():
        local_val = tax_facts.get(key)
        if local_val is None:
            mismatches.append(
                {
                    "field": key,
                    "severity": "missing-doc",
                    "description": "Value exists in AIS but not extracted from docs.",
                    "ais_value": ais_val,
                    "our_value": None,
                }
            )
            continue

        if isinstance(ais_val, (int, float)) and isinstance(local_val, (int, float)):
            denom = max(abs(float(ais_val)), 1.0)
            ratio = abs(float(ais_val) - float(local_val)) / denom
            if ratio > 0:
                mismatches.append(
                    {
                        "field": key,
                        "severity": _severity(ratio),
                        "description": "Numeric value differs between AIS and extracted facts.",
                        "ais_value": ais_val,
                        "our_value": local_val,
                    }
                )
        elif ais_val != local_val:
            mismatches.append(
                {
                    "field": key,
                    "severity": "human-decision",
                    "description": "Non-numeric value mismatch requiring user confirmation.",
                    "ais_value": ais_val,
                    "our_value": local_val,
                }
            )

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"Reconciliation complete: {len(mismatches)} mismatches detected.",
            "metadata": {"node": "reconcile"},
        }
    )

    state.apply_update({"messages": messages, "reconciliation": {"mismatches": mismatches}})
    return state
