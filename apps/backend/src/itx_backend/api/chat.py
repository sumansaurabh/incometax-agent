from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.security.request_auth import require_thread_state
from itx_backend.services.chat import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    thread_id: str
    message: str
    context: Optional[dict[str, Any]] = None


@router.post("/message")
async def chat_message(payload: ChatMessageRequest) -> dict[str, Any]:
    await require_thread_state(payload.thread_id)
    return await chat_service.handle_message(
        thread_id=payload.thread_id,
        message=payload.message,
        context=payload.context,
    )


@router.get("/{thread_id}/messages")
async def chat_history(thread_id: str, limit: int = 50) -> dict[str, Any]:
    await require_thread_state(thread_id)
    return {
        "thread_id": thread_id,
        "messages": await chat_service.list_messages(thread_id, limit=limit),
    }
