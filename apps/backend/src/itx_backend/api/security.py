from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel

from itx_backend.security.request_auth import get_request_auth, require_thread_state
from itx_backend.security.anomaly import anomaly_detector
from itx_backend.security.quarantine import current_quarantine_status, quarantine_thread, resume_thread
from itx_backend.services.retention import retention_service

router = APIRouter(prefix="/api/security", tags=["security"])


class QuarantineRequest(BaseModel):
    thread_id: str
    reason: str = "anomaly_detected"
    details: dict = {}


class ResumeQuarantineRequest(BaseModel):
    note: str | None = None


@router.get("/anomalies")
async def anomalies(limit: int = 50) -> dict:
    get_request_auth(required=True)
    return {"items": anomaly_detector.recent(limit=limit)}


@router.post("/purges/run")
async def run_due_purges(limit: int = 10) -> dict:
    get_request_auth(required=True)
    processed = await retention_service.process_due_purges(limit=limit)
    return {"items": processed, "count": len(processed)}


@router.get("/purges/{thread_id}")
async def purge_status(thread_id: str) -> dict:
    await require_thread_state(thread_id)
    try:
        items = await retention_service.list_purge_jobs(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="purge_job_not_found") from exc
    return {"thread_id": thread_id, "items": items}


@router.post("/quarantine")
async def quarantine(payload: QuarantineRequest) -> dict:
    auth = get_request_auth(required=True)
    await require_thread_state(payload.thread_id)
    try:
        status = await quarantine_thread(
            payload.thread_id,
            requested_by=auth.user_id,
            reason=payload.reason,
            details=payload.details,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc
    return {"thread_id": payload.thread_id, "security_status": status}


@router.get("/quarantine/{thread_id}")
async def quarantine_status(thread_id: str) -> dict:
    state = await require_thread_state(thread_id)
    return {"thread_id": thread_id, "security_status": current_quarantine_status(state)}


@router.post("/quarantine/{thread_id}/resume")
async def resume_quarantine(thread_id: str, payload: ResumeQuarantineRequest) -> dict:
    auth = get_request_auth(required=True)
    await require_thread_state(thread_id)
    try:
        status = await resume_thread(thread_id, requested_by=auth.user_id, note=payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc
    return {"thread_id": thread_id, "security_status": status}
