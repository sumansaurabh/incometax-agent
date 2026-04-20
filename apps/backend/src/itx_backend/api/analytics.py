from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.services.analytics import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class TrackEventRequest(BaseModel):
    event_type: str
    stage: str
    thread_id: str
    payload: dict = {}


@router.post("/track")
def track(payload: TrackEventRequest) -> dict[str, str]:
    analytics_service.track(
        event_type=payload.event_type,
        stage=payload.stage,
        thread_id=payload.thread_id,
        payload=payload.payload,
    )
    return {"status": "ok"}


@router.get("/dashboard")
def dashboard() -> dict:
    return analytics_service.dashboard()


@router.get("/timeline/{thread_id}")
def timeline(thread_id: str) -> dict:
    return {"items": analytics_service.timeline(thread_id)}
