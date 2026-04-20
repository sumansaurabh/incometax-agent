from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    state.archived = True
    state.current_node = "done"
    state.messages.append("Thread archived")
    return state
