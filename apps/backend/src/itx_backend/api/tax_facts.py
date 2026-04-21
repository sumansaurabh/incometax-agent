from fastapi import APIRouter

from itx_backend.agent.checkpointer import checkpointer

router = APIRouter(prefix="/api/tax-facts", tags=["tax-facts"])


@router.get("/{thread_id}")
async def tax_facts(thread_id: str) -> dict[str, object]:
    state = await checkpointer.latest(thread_id)
    if not state:
        return {"error": "thread_not_found"}
    return {
        "thread_id": thread_id,
        "facts": state.tax_facts,
        "fact_evidence": state.fact_evidence,
        "reconciliation": state.reconciliation,
    }
