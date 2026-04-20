from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("validate_response node placeholder")
    return state
