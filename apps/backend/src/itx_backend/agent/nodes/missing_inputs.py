from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("missing_inputs node placeholder")
    return state
