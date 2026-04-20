from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("submission_summary node placeholder")
    return state
