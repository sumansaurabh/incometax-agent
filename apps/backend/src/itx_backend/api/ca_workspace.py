from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.security.request_auth import filter_owned_states, get_request_auth, require_thread_state
from itx_backend.services.action_runtime import action_runtime
from itx_backend.services.review_workspace import assess_agent_state, review_workspace


class PrepareHandoffRequest(BaseModel):
    thread_id: str
    reason: Optional[str] = None

router = APIRouter(prefix="/api/ca", tags=["ca-workspace"])


@router.get("/clients")
async def clients() -> dict:
    activity_cache = {}
    items = []
    for latest in await filter_owned_states(await checkpointer.list_latest_states()):
        activity_cache[latest.thread_id] = await action_runtime.list_thread_activity(latest.thread_id)
        pending_approvals = [
            approval
            for approval in activity_cache[latest.thread_id].get("approvals", [])
            if approval.get("status") == "pending"
        ]
        tax_facts = latest.tax_facts or {}
        submission = latest.submission_summary or {}
        support_assessment = assess_agent_state(latest, activity_cache[latest.thread_id])
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
                "support_mode": support_assessment["mode"],
                "can_autofill": support_assessment["can_autofill"],
                "last_execution": activity_cache[latest.thread_id].get("executions", [None])[0],
            }
        )
    return {"items": items}


@router.get("/client/{thread_id}")
async def client_detail(thread_id: str) -> dict:
    state = await require_thread_state(thread_id)
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
        "support_assessment": assess_agent_state(state, activity),
        "handoffs": await review_workspace.list_handoffs(thread_id),
    }


@router.get("/client/{thread_id}/support")
async def client_support(thread_id: str) -> dict:
    await require_thread_state(thread_id)
    try:
        return await review_workspace.support_assessment(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc


@router.post("/handoffs/prepare")
async def prepare_handoff(payload: PrepareHandoffRequest) -> dict:
    await require_thread_state(payload.thread_id)
    auth = get_request_auth(required=True)
    try:
        return await review_workspace.prepare_handoff(
            thread_id=payload.thread_id,
            requested_by_user_id=auth.user_id,
            requested_by_email=auth.email,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc


@router.get("/handoffs/{thread_id}")
async def handoffs(thread_id: str) -> dict:
    await require_thread_state(thread_id)
    return {"thread_id": thread_id, "items": await review_workspace.list_handoffs(thread_id)}


@router.get("/handoffs/{thread_id}/{handoff_id}/package")
async def download_handoff_package(thread_id: str, handoff_id: str) -> Response:
    await require_thread_state(thread_id)
    try:
        content, media_type, filename = await review_workspace.read_handoff_package(thread_id, handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="handoff_not_found") from exc

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
