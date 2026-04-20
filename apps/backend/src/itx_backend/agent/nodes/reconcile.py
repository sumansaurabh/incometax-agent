from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("reconcile node placeholder")
    return state
