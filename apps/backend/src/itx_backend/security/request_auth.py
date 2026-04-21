from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Iterable, Optional

from fastapi import HTTPException

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.services.auth_runtime import AuthContext


_request_auth: ContextVar[Optional[AuthContext]] = ContextVar("itx_request_auth", default=None)


def set_request_auth(context: AuthContext) -> Token[Optional[AuthContext]]:
    return _request_auth.set(context)


def reset_request_auth(token: Token[Optional[AuthContext]]) -> None:
    _request_auth.reset(token)


def get_request_auth(required: bool = True) -> Optional[AuthContext]:
    context = _request_auth.get()
    if required and context is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return context


async def require_thread_state(thread_id: str) -> AgentState:
    state = await checkpointer.latest(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")
    auth = get_request_auth(required=True)
    if state.user_id != auth.user_id:
        raise HTTPException(status_code=403, detail="thread_forbidden")
    return state


async def require_thread_history(thread_id: str) -> list[AgentState]:
    history = await checkpointer.history(thread_id)
    if not history:
        raise HTTPException(status_code=404, detail="thread_not_found")
    auth = get_request_auth(required=True)
    if any(state.user_id != auth.user_id for state in history):
        raise HTTPException(status_code=403, detail="thread_forbidden")
    return history


async def filter_owned_states(states: Iterable[AgentState]) -> list[AgentState]:
    auth = get_request_auth(required=True)
    return [state for state in states if state.user_id == auth.user_id]