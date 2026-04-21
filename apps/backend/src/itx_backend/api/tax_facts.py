from fastapi import APIRouter

router = APIRouter(prefix="/api/tax-facts", tags=["tax-facts"])


@router.get("/{thread_id}")
async def tax_facts(thread_id: str) -> dict[str, object]:
    return {"thread_id": thread_id, "facts": []}
