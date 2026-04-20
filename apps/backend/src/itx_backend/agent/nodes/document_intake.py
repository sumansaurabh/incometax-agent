from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("document_intake node placeholder")
    return state
