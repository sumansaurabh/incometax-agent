from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("infer_itr node placeholder")
    return state
