from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("fill_plan node placeholder")
    return state
