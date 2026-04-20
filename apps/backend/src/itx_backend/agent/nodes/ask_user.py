from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.current_node = "archive"
    state.messages.append("Please confirm detected details.")
    return state
