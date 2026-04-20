import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.graph import graph
from itx_backend.agent.state import AgentState

router = APIRouter(prefix="/api/threads", tags=["threads"])


class ThreadStartRequest(BaseModel):
    user_id: str


@router.post("/start")
def start_thread(payload: ThreadStartRequest) -> AgentState:
    state = AgentState(thread_id=str(uuid.uuid4()), user_id=payload.user_id)
    final_state = graph.run(state)
    checkpointer.save(final_state)
    return final_state


@router.get("/{thread_id}")
def get_thread(thread_id: str) -> AgentState | dict[str, str]:
    state = checkpointer.latest(thread_id)
    if not state:
        return {"error": "thread_not_found"}
    return state
