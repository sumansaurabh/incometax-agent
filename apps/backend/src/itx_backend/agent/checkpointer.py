from collections import defaultdict

from itx_backend.agent.state import AgentState


class InMemoryCheckpointer:
    def __init__(self) -> None:
        self._store: dict[str, list[AgentState]] = defaultdict(list)

    def save(self, state: AgentState) -> None:
        self._store[state.thread_id].append(state.model_copy(deep=True))

    def latest(self, thread_id: str) -> AgentState | None:
        items = self._store.get(thread_id, [])
        return items[-1] if items else None

    def list_thread_ids(self) -> list[str]:
        return list(self._store.keys())

    def history(self, thread_id: str) -> list[AgentState]:
        return list(self._store.get(thread_id, []))


checkpointer = InMemoryCheckpointer()
