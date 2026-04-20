from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("recovery node placeholder")
    return state
