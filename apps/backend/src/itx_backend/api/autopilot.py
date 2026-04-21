from fastapi import APIRouter

from itx_backend.services.portal_drift_autopilot import portal_drift_autopilot
from itx_backend.telemetry.drift import get_drift_telemetry

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


@router.post("/portal-drift")
async def run_portal_drift_autopilot() -> dict:
    items = get_drift_telemetry().export_for_training()
    return portal_drift_autopilot.run(items)
