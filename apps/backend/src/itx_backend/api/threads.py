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
    force_new: bool = False


@router.post("/start")
async def start_thread(payload: ThreadStartRequest) -> AgentState:
    auth = get_request_auth(required=False)
    user_id = auth.user_id if auth else payload.user_id
    if not user_id:
        raise ValueError("user_id_required")
    state = AgentState(thread_id=str(uuid.uuid4()), user_id=user_id)
    await analytics_service.track("thread_started", "bootstrap", state.thread_id, {"user_id": user_id})
    final_state = await graph.run(state)
    await analytics_service.track("thread_completed", "archive", state.thread_id, {"archived": final_state.archived})
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

    if not payload.force_new:
        # Look up the most recent non-archived thread for this user before
        # creating a new one.  This prevents the sidepanel from generating a
        # fresh thread_id on every session restart, which would lose visibility
        # of documents uploaded on an earlier thread (e.g. via the dashboard).
        existing_for_user = await checkpointer.latest_for_user(user_id)
        if existing_for_user is not None:
            await analytics_service.track("thread_ensured", "reuse", existing_for_user.thread_id, {"user_id": user_id})
            return existing_for_user

    state = AgentState(thread_id=str(uuid.uuid4()), user_id=user_id)
    await checkpointer.save(state)
    await analytics_service.track("thread_ensured", "bootstrap", state.thread_id, {"user_id": user_id})
    return state


@router.get("/mine")
async def list_my_threads() -> dict[str, Any]:
    """Return all threads belonging to the authenticated user."""
    auth = get_request_auth(required=True)
    states = await checkpointer.list_for_user(auth.user_id)
    threads = []
    for state in states:
        # Count documents per thread for the summary
        doc_count = 0
        try:
            from itx_backend.services.documents import document_service
            docs = await document_service.list_documents(state.thread_id)
            doc_count = len(docs)
        except Exception:
            pass
        threads.append({
            "thread_id": state.thread_id,
            "user_id": state.user_id,
            "current_node": state.current_node,
            "itr_type": state.itr_type,
            "submission_status": state.submission_status,
            "archived": state.archived,
            "document_count": doc_count,
        })
    return {"threads": threads}


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
