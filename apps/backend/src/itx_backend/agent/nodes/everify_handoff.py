from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("everify_handoff node placeholder")
    return state
