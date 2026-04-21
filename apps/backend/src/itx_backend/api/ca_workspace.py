from fastapi import APIRouter

from itx_backend.agent.checkpointer import checkpointer

router = APIRouter(prefix="/api/ca", tags=["ca-workspace"])


@router.get("/clients")
async def clients() -> dict:
    items = []
    for latest in await checkpointer.list_latest_states():
        tax_facts = latest.tax_facts or {}
        submission = latest.submission_summary or {}
        items.append(
            {
                "thread_id": latest.thread_id,
                "pan": tax_facts.get("pan"),
                "name": tax_facts.get("name"),
                "itr_type": latest.itr_type,
                "assessment_year": submission.get("assessment_year"),
                "can_submit": submission.get("can_submit"),
                "blocking_issues": submission.get("blocking_issues", []),
                "mismatch_count": len((latest.reconciliation or {}).get("mismatches", [])),
            }
        )
    return {"items": items}


@router.get("/client/{thread_id}")
async def client_detail(thread_id: str) -> dict:
    state = await checkpointer.latest(thread_id)
    if not state:
        return {"error": "thread_not_found"}
    return {
        "thread_id": thread_id,
        "tax_facts": state.tax_facts,
        "reconciliation": state.reconciliation,
        "submission_summary": state.submission_summary or {},
        "pending_approvals": state.pending_approvals,
        "documents": state.documents,
        "messages": state.messages,
    }
