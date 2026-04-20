from fastapi import APIRouter

from itx_backend.agent.checkpointer import checkpointer

router = APIRouter(prefix="/api/ca", tags=["ca-workspace"])


@router.get("/clients")
def clients() -> dict:
    items = []
    for thread_id in checkpointer.list_thread_ids():
        latest = checkpointer.latest(thread_id)
        if not latest:
            continue
        tax_facts = latest.get("tax_facts", {})
        submission = latest.get("submission_summary", {})
        items.append(
            {
                "thread_id": thread_id,
                "pan": tax_facts.get("pan"),
                "name": tax_facts.get("name"),
                "itr_type": latest.get("itr_type"),
                "assessment_year": submission.get("assessment_year"),
                "can_submit": submission.get("can_submit"),
                "blocking_issues": submission.get("blocking_issues", []),
            }
        )
    return {"items": items}


@router.get("/client/{thread_id}")
def client_detail(thread_id: str) -> dict:
    state = checkpointer.latest(thread_id)
    if not state:
        return {"error": "thread_not_found"}
    return {
        "thread_id": thread_id,
        "tax_facts": state.get("tax_facts", {}),
        "submission_summary": state.get("submission_summary", {}),
        "pending_approvals": state.get("pending_approvals", []),
        "messages": state.get("messages", []),
    }
