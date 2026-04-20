from fastapi import APIRouter
from pydantic import BaseModel

from itx_backend.services.offline_export import offline_exporter

router = APIRouter(prefix="/api/exports", tags=["exports"])


class OfflineExportRequest(BaseModel):
    assessment_year: str
    itr_type: str
    tax_facts: dict


@router.post("/offline-json")
def export_offline_json(payload: OfflineExportRequest) -> dict:
    result = offline_exporter.export(
        tax_facts=payload.tax_facts,
        assessment_year=payload.assessment_year,
        itr_type=payload.itr_type,
    )
    return {"artifact": result}
