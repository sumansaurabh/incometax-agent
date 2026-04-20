from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
    if state.portal_page == "unknown":
        state.portal_page = "dashboard"
    state.current_page = state.portal_page
    state.current_node = "ask_user"
    state.messages.append(f"Detected page: {state.portal_page}")
    return state
