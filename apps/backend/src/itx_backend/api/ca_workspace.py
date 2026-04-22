from typing import Optional

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from itx_backend.security.request_auth import get_request_auth
from itx_backend.services.analytics import analytics_service
from itx_backend.services.consent import missing_purposes
from itx_backend.services.filing_runtime import filing_runtime
from itx_backend.services.action_runtime import action_runtime
from itx_backend.services.review_workspace import assess_agent_state, review_workspace


class PrepareHandoffRequest(BaseModel):
    thread_id: str
    reason: Optional[str] = None


class ReviewerSignoffRequest(BaseModel):
    thread_id: str
    approval_id: str
    reviewer_email: str
    note: Optional[str] = None


class ReviewerDecisionRequest(BaseModel):
    approved: bool
    note: Optional[str] = None


class CounterConsentRequest(BaseModel):
    approved: bool = True
    note: Optional[str] = None


class BulkExportRequest(BaseModel):
    thread_ids: Optional[list[str]] = None

router = APIRouter(prefix="/api/ca", tags=["ca-workspace"])


async def _require_accessible_state(thread_id: str):
    auth = get_request_auth(required=True)
    try:
        return await review_workspace.get_accessible_state(
            thread_id=thread_id,
            user_id=auth.user_id,
            email=auth.email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="thread_forbidden") from exc


async def _require_consents(thread_id: str, purposes: list[str]) -> None:
    consents = await filing_runtime.list_consents(thread_id)
    missing = missing_purposes(consents, purposes)
    if missing:
        raise HTTPException(status_code=409, detail=f"missing_consent_purposes:{','.join(missing)}")


async def _serialize_client_item(latest, access_role: str) -> dict:
    activity = await action_runtime.list_thread_activity(latest.thread_id)
    signoffs = await review_workspace.list_signoffs(latest.thread_id)
    pending_approvals = [
        approval
        for approval in activity.get("approvals", [])
        if approval.get("status") == "pending"
    ]
    pending_signoffs = [signoff for signoff in signoffs if signoff.get("status") != "client_approved"]
    tax_facts = latest.tax_facts or {}
    submission = latest.submission_summary or {}
    support_assessment = assess_agent_state(latest, activity)
    executions = activity.get("executions", [])
    return {
        "thread_id": latest.thread_id,
        "pan": tax_facts.get("pan"),
        "name": tax_facts.get("name"),
        "itr_type": latest.itr_type,
        "assessment_year": submission.get("assessment_year"),
        "can_submit": submission.get("can_submit"),
        "blocking_issues": submission.get("blocking_issues", []),
        "mismatch_count": len((latest.reconciliation or {}).get("mismatches", [])),
        "pending_approval_count": len(pending_approvals),
        "pending_signoff_count": len(pending_signoffs),
        "access_role": access_role,
        "support_mode": support_assessment["mode"],
        "can_autofill": support_assessment["can_autofill"],
        "last_execution": executions[0] if executions else None,
    }


@router.get("/clients")
async def clients() -> dict:
    auth = get_request_auth(required=True)
    items = []
    for latest, access_role in await review_workspace.list_accessible_states(user_id=auth.user_id, email=auth.email):
        items.append(await _serialize_client_item(latest, access_role))
    return {"items": items}


@router.get("/dashboard")
async def dashboard() -> dict:
    auth = get_request_auth(required=True)
    items = [
        await _serialize_client_item(latest, access_role)
        for latest, access_role in await review_workspace.list_accessible_states(user_id=auth.user_id, email=auth.email)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": {"user_id": auth.user_id, "email": auth.email},
        "clients": items,
        "analytics": await analytics_service.dashboard(),
    }


@router.get("/client/{thread_id}")
async def client_detail(thread_id: str) -> dict:
    state, access_role = await _require_accessible_state(thread_id)
    activity = await action_runtime.list_thread_activity(thread_id)
    return {
        "thread_id": thread_id,
        "access_role": access_role,
        "tax_facts": state.tax_facts,
        "reconciliation": state.reconciliation,
        "submission_summary": state.submission_summary or {},
        "pending_approvals": state.pending_approvals,
        "documents": state.documents,
        "actions": activity,
        "messages": state.messages,
        "support_assessment": assess_agent_state(state, activity),
        "handoffs": await review_workspace.list_handoffs(thread_id),
        "reviewer_signoffs": await review_workspace.list_signoffs(thread_id),
        "shares": await review_workspace.list_access_grants(thread_id=thread_id),
    }


@router.get("/client/{thread_id}/support")
async def client_support(thread_id: str) -> dict:
    await _require_accessible_state(thread_id)
    try:
        return await review_workspace.support_assessment(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc


@router.get("/client/{thread_id}/export")
async def download_client_export(thread_id: str) -> Response:
    auth = get_request_auth(required=True)
    await _require_consents(thread_id, ["share_with_reviewer", "export_filing_bundle"])
    try:
        content, filename = await review_workspace.build_client_export_bundle(
            thread_id=thread_id,
            user_id=auth.user_id,
            email=auth.email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="thread_not_found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/exports/bulk")
async def download_bulk_export(payload: BulkExportRequest) -> Response:
    auth = get_request_auth(required=True)
    try:
        content, filename = await review_workspace.build_bulk_export_bundle(
            user_id=auth.user_id,
            email=auth.email,
            thread_ids=payload.thread_ids,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/handoffs/prepare")
async def prepare_handoff(payload: PrepareHandoffRequest) -> dict:
    auth = get_request_auth(required=True)
    await _require_accessible_state(payload.thread_id)
    await _require_consents(payload.thread_id, ["share_with_reviewer", "share_review_summary", "share_supporting_documents"])
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
    await _require_accessible_state(thread_id)
    return {"thread_id": thread_id, "items": await review_workspace.list_handoffs(thread_id)}


@router.get("/handoffs/{thread_id}/{handoff_id}/package")
async def download_handoff_package(thread_id: str, handoff_id: str) -> Response:
    await _require_accessible_state(thread_id)
    try:
        content, media_type, filename = await review_workspace.read_handoff_package(thread_id, handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="handoff_not_found") from exc

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/client/{thread_id}/signoffs")
async def signoffs(thread_id: str) -> dict:
    await _require_accessible_state(thread_id)
    return {"thread_id": thread_id, "items": await review_workspace.list_signoffs(thread_id)}


@router.post("/reviewers/signoff/request")
async def request_reviewer_signoff(payload: ReviewerSignoffRequest) -> dict:
    auth = get_request_auth(required=True)
    state, access_role = await _require_accessible_state(payload.thread_id)
    await _require_consents(payload.thread_id, ["share_with_reviewer", "share_review_summary"])
    if access_role != "owner" or state.user_id != auth.user_id:
        raise HTTPException(status_code=403, detail="reviewer_signoff_owner_required")
    try:
        return await review_workspace.request_signoff(
            thread_id=payload.thread_id,
            approval_key=payload.approval_id,
            owner_user_id=auth.user_id,
            reviewer_email=payload.reviewer_email,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval_not_found") from exc


@router.post("/reviewers/signoff/{signoff_id}/decision")
async def reviewer_decision(signoff_id: str, payload: ReviewerDecisionRequest) -> dict:
    auth = get_request_auth(required=True)
    try:
        return await review_workspace.reviewer_decision(
            signoff_id=signoff_id,
            reviewer_user_id=auth.user_id,
            reviewer_email=auth.email,
            approved=payload.approved,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="reviewer_signoff_not_found") from exc


@router.post("/reviewers/signoff/{signoff_id}/counter-consent")
async def reviewer_counter_consent(signoff_id: str, payload: CounterConsentRequest) -> dict:
    auth = get_request_auth(required=True)
    try:
        return await review_workspace.client_counter_consent(
            signoff_id=signoff_id,
            owner_user_id=auth.user_id,
            approved=payload.approved,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="reviewer_signoff_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
