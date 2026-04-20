from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.messages.append("execute_actions node placeholder")
    return state
