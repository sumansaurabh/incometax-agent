from itx_backend.agent.nodes import archive, ask_user, bootstrap, portal_scan
from itx_backend.agent.state import AgentState


class AgentGraph:
    def run(self, state: AgentState) -> AgentState:
        state = bootstrap.run(state)
        state = portal_scan.run(state)
        state = ask_user.run(state)
        state = archive.run(state)
        return state


graph = AgentGraph()
