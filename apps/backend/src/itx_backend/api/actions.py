from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ActionDecision(BaseModel):
    proposal_id: str
    approved: bool


@router.post("/decision")
def decision(payload: ActionDecision) -> dict[str, str]:
    status = "approved" if payload.approved else "rejected"
    return {"proposal_id": payload.proposal_id, "status": status}
