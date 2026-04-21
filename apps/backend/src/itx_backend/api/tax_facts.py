from fastapi import APIRouter

from itx_backend.security.request_auth import require_thread_state

router = APIRouter(prefix="/api/tax-facts", tags=["tax-facts"])


@router.get("/{thread_id}")
async def tax_facts(thread_id: str) -> dict[str, object]:
    state = await require_thread_state(thread_id)
    return {
        "thread_id": thread_id,
        "facts": state.tax_facts,
        "fact_evidence": state.fact_evidence,
        "reconciliation": state.reconciliation,
    }
