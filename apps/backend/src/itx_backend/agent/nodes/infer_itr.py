from __future__ import annotations

from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    facts = state.get("tax_facts", {})

    has_business = bool(facts.get("business_income"))
    has_capital_gains = bool(facts.get("capital_gains"))
    has_foreign_assets = bool(facts.get("foreign_assets"))
    presumptive = bool(facts.get("presumptive_taxation"))
    total_income = float(facts.get("total_income", 0) or 0)

    inferred = "ITR-1"
    if has_business and presumptive and total_income <= 5000000:
        inferred = "ITR-4"
    elif has_business:
        inferred = "ITR-3"
    elif has_capital_gains or has_foreign_assets or total_income > 5000000:
        inferred = "ITR-2"

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"ITR inferred: {inferred}",
            "metadata": {"node": "infer_itr", "itr_type": inferred},
        }
    )

    state.apply_update({"messages": messages, "itr_type": inferred})
    return state
