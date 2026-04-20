from fastapi import APIRouter

from itx_backend.security.anomaly import anomaly_detector

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/anomalies")
def anomalies(limit: int = 50) -> dict:
    return {"items": anomaly_detector.recent(limit=limit)}
