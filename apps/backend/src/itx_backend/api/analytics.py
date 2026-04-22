from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from itx_backend.security.request_auth import get_request_auth, require_thread_state
from itx_backend.services.analytics import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class TrackEventRequest(BaseModel):
    event_type: str
    stage: str
    thread_id: str
    payload: dict = {}


@router.post("/track")
async def track(payload: TrackEventRequest) -> dict[str, str]:
    await require_thread_state(payload.thread_id)
    await analytics_service.track(
        event_type=payload.event_type,
        stage=payload.stage,
        thread_id=payload.thread_id,
        payload=payload.payload,
    )
    return {"status": "ok"}


@router.get("/dashboard")
async def dashboard() -> dict:
    get_request_auth(required=True)
    return await analytics_service.dashboard()


@router.get("/timeline/{thread_id}")
async def timeline(thread_id: str) -> dict:
    await require_thread_state(thread_id)
    return {"items": await analytics_service.timeline(thread_id)}


@router.get("/agent-events")
async def agent_events(thread_id: Optional[str] = None, limit: int = 50) -> dict:
    get_request_auth(required=True)
    if thread_id is not None:
        await require_thread_state(thread_id)
    return {"items": await analytics_service.agent_events(thread_id=thread_id, limit=limit)}
