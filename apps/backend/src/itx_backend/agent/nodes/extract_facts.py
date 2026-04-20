from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("extract_facts node placeholder")
    return state
