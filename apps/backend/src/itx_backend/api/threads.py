from __future__ import annotations

import uuid
from typing import Any, Optional, Union

from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.graph import graph
from itx_backend.agent.state import AgentState
from itx_backend.services.analytics import analytics_service

router = APIRouter(prefix="/api/threads", tags=["threads"])


class ThreadStartRequest(BaseModel):
    user_id: str


class ThreadEnsureRequest(BaseModel):
    user_id: str
    thread_id: Optional[str] = None


@router.post("/start")
async def start_thread(payload: ThreadStartRequest) -> AgentState:
    state = AgentState(thread_id=str(uuid.uuid4()), user_id=payload.user_id)
    analytics_service.track("thread_started", "bootstrap", state.thread_id, {"user_id": payload.user_id})
    final_state = await graph.run(state)
    analytics_service.track("thread_completed", "archive", state.thread_id, {"archived": final_state.archived})
    return final_state


@router.post("/ensure")
async def ensure_thread(payload: ThreadEnsureRequest) -> AgentState:
    if payload.thread_id:
        existing = await checkpointer.latest(payload.thread_id)
        if existing:
            return existing

    state = AgentState(thread_id=payload.thread_id or str(uuid.uuid4()), user_id=payload.user_id)
    await checkpointer.save(state)
    analytics_service.track("thread_ensured", "bootstrap", state.thread_id, {"user_id": payload.user_id})
    return state


@router.get("/{thread_id}")
async def get_thread(thread_id: str) -> Union[AgentState, dict[str, str]]:
    state = await checkpointer.latest(thread_id)
    if not state:
        return {"error": "thread_not_found"}
    return state


@router.get("/{thread_id}/history")
async def get_thread_history(thread_id: str) -> dict[str, Any]:
    history = await checkpointer.history(thread_id)
    if not history:
        return {"error": "thread_not_found"}
    return {
        "thread_id": thread_id,
        "checkpoints": [state.model_dump(mode="json") for state in history],
    }
