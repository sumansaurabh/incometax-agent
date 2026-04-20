from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.telemetry.drift import (
    DriftSeverity,
    DriftType,
    get_drift_telemetry,
)

router = APIRouter(prefix="/api/drift", tags=["drift"])


class DriftEventRequest(BaseModel):
    drift_type: DriftType
    severity: DriftSeverity
    page_type: str
    selector: str
    url: str
    expected: str | None = None
    actual: str | None = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    metadata: dict = {}


@router.post("/event")
def create_event(payload: DriftEventRequest) -> dict:
    event = get_drift_telemetry().log_drift(
        drift_type=payload.drift_type,
        severity=payload.severity,
        page_type=payload.page_type,
        selector=payload.selector,
        url=payload.url,
        expected=payload.expected,
        actual=payload.actual,
        recovery_attempted=payload.recovery_attempted,
        recovery_successful=payload.recovery_successful,
        metadata=payload.metadata,
    )
    return {"event_id": event.event_id}


@router.get("/stats")
def stats() -> dict:
    return get_drift_telemetry().get_statistics()


@router.get("/training-export")
def training_export() -> dict:
    return {"items": get_drift_telemetry().export_for_training()}
