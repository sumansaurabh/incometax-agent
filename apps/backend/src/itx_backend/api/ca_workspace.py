from fastapi import APIRouter

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.services.action_runtime import action_runtime

router = APIRouter(prefix="/api/ca", tags=["ca-workspace"])


@router.get("/clients")
async def clients() -> dict:
    activity_cache = {}
    items = []
    for latest in await checkpointer.list_latest_states():
        activity_cache[latest.thread_id] = await action_runtime.list_thread_activity(latest.thread_id)
        pending_approvals = [
            approval
            for approval in activity_cache[latest.thread_id].get("approvals", [])
            if approval.get("status") == "pending"
        ]
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
                "pending_approval_count": len(pending_approvals),
                "last_execution": activity_cache[latest.thread_id].get("executions", [None])[0],
            }
        )
    return {"items": items}


@router.get("/client/{thread_id}")
async def client_detail(thread_id: str) -> dict:
    state = await checkpointer.latest(thread_id)
    if not state:
        return {"error": "thread_not_found"}
    activity = await action_runtime.list_thread_activity(thread_id)
    return {
        "thread_id": thread_id,
        "tax_facts": state.tax_facts,
        "reconciliation": state.reconciliation,
        "submission_summary": state.submission_summary or {},
        "pending_approvals": state.pending_approvals,
        "documents": state.documents,
        "actions": activity,
        "messages": state.messages,
    }
