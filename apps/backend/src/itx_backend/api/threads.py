from __future__ import annotations

import uuid
from typing import Any, Optional, Union

from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.graph import graph
from itx_backend.agent.state import AgentState
from itx_backend.security.request_auth import get_request_auth, require_thread_history, require_thread_state
from itx_backend.services.analytics import analytics_service

router = APIRouter(prefix="/api/threads", tags=["threads"])


class ThreadStartRequest(BaseModel):
    user_id: Optional[str] = None


class ThreadEnsureRequest(BaseModel):
    user_id: Optional[str] = None
    thread_id: Optional[str] = None


@router.post("/start")
async def start_thread(payload: ThreadStartRequest) -> AgentState:
    auth = get_request_auth(required=False)
    user_id = auth.user_id if auth else payload.user_id
    if not user_id:
        raise ValueError("user_id_required")
    state = AgentState(thread_id=str(uuid.uuid4()), user_id=user_id)
    analytics_service.track("thread_started", "bootstrap", state.thread_id, {"user_id": user_id})
    final_state = await graph.run(state)
    analytics_service.track("thread_completed", "archive", state.thread_id, {"archived": final_state.archived})
    return final_state


@router.post("/ensure")
async def ensure_thread(payload: ThreadEnsureRequest) -> AgentState:
    auth = get_request_auth(required=False)
    user_id = auth.user_id if auth else payload.user_id
    if not user_id:
        raise ValueError("user_id_required")
    if payload.thread_id:
        existing = await require_thread_state(payload.thread_id)
        return existing

    state = AgentState(thread_id=payload.thread_id or str(uuid.uuid4()), user_id=user_id)
    await checkpointer.save(state)
    analytics_service.track("thread_ensured", "bootstrap", state.thread_id, {"user_id": user_id})
    return state


@router.get("/{thread_id}")
async def get_thread(thread_id: str) -> Union[AgentState, dict[str, str]]:
    return await require_thread_state(thread_id)


@router.get("/{thread_id}/history")
async def get_thread_history(thread_id: str) -> dict[str, Any]:
    history = await require_thread_history(thread_id)
    return {
        "thread_id": thread_id,
        "checkpoints": [state.model_dump(mode="json") for state in history],
    }
