from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.current_node = "portal_scan"
    state.messages.append("Bootstrap complete")
    return state
