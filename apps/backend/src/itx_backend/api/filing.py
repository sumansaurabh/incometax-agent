from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.nodes import approval_gate, archive, everify_handoff, revised_return, submission_summary
from itx_backend.agent.state import AgentState
from itx_backend.security.quarantine import ensure_thread_not_quarantined
from itx_backend.security.request_auth import get_request_auth, require_thread_state
from itx_backend.services.filing_runtime import filing_runtime
from itx_backend.services.official_artifacts import prepare_official_artifact_attachment
from itx_backend.services.post_filing import (
    assessment_year_for_state,
    build_next_ay_checklist,
    build_refund_status_capture,
    build_year_over_year_comparison,
    prepare_notice_response,
    select_prior_filed_state,
)
from itx_backend.services.regime_advisor import compare_regimes
from itx_backend.services.retention import retention_service

router = APIRouter(prefix="/api/filing", tags=["filing"])


class FilingSummaryRequest(BaseModel):
    thread_id: str
    is_final: bool = True


class SubmitPrepareRequest(BaseModel):
    thread_id: str
    is_final: bool = True


class CompleteSubmissionRequest(BaseModel):
    thread_id: str
    ack_no: Optional[str] = None
    portal_ref: Optional[str] = None
    filed_at: Optional[str] = None
    itr_v_text: Optional[str] = None


class OfficialArtifactAttachmentRequest(BaseModel):
    thread_id: str
    artifact_kind: str = "itr_v"
    page_type: Optional[str] = None
    page_title: Optional[str] = None
    page_url: Optional[str] = None
    portal_state: Optional[dict[str, Any]] = None
    manual_text: Optional[str] = None
    ack_no: Optional[str] = None
    portal_ref: Optional[str] = None
    filed_at: Optional[str] = None


class EVerifyPrepareRequest(BaseModel):
    thread_id: str
    method: str


class EVerifyStartRequest(BaseModel):
    thread_id: str
    method: Optional[str] = None


class EVerifyCompleteRequest(BaseModel):
    thread_id: str
    handoff_id: str
    portal_ref: Optional[str] = None
    verified_at: Optional[str] = None


class RevisionCreateRequest(BaseModel):
    thread_id: str
    reason: str
    revision_number: int = 1


class ConsentRevokeRequest(BaseModel):
    thread_id: str
    consent_id: str
    reason: str = "user_revoked_consent"
    process_immediately: bool = True


class RegimePreviewRequest(BaseModel):
    thread_id: str


class YearOverYearRequest(BaseModel):
    thread_id: str


class NextAyChecklistRequest(BaseModel):
    thread_id: str


class NoticePreparationRequest(BaseModel):
    thread_id: str
    notice_text: str
    notice_type: str = "143(1)"


class RefundStatusCaptureRequest(BaseModel):
    thread_id: str
    page_type: Optional[str] = None
    page_title: Optional[str] = None
    page_url: Optional[str] = None
    portal_state: Optional[dict[str, Any]] = None
    manual_status: Optional[str] = None
    manual_portal_ref: Optional[str] = None
    manual_refund_amount: Optional[Any] = None
    manual_issued_at: Optional[str] = None
    manual_processed_at: Optional[str] = None
    manual_refund_mode: Optional[str] = None
    manual_bank_masked: Optional[str] = None


def _require_state(state: Optional[AgentState]) -> AgentState:
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")
    return state


def _latest_node_message(state: AgentState, node_name: str) -> str:
    for message in reversed(state.messages):
        if isinstance(message, dict) and message.get("metadata", {}).get("node") == node_name:
            return str(message.get("content", ""))
    return ""


async def _refresh_submission_summary(state: AgentState, *, is_final: bool) -> tuple[AgentState, dict[str, Any]]:
    result = await submission_summary.submission_summary(state)
    state.apply_update(result)
    if state.pending_submission:
        state.pending_submission["is_final"] = is_final
    state.submission_status = "ready_to_submit" if state.pending_submission else "blocked"
    summary_record = await filing_runtime.record_submission_summary(
        thread_id=state.thread_id,
        itr_type=state.itr_type,
        regime=state.submission_summary.get("regime") if state.submission_summary else None,
        tax_facts=state.tax_facts,
        submission_summary=state.submission_summary or {},
        summary_markdown=_latest_node_message(state, "submission_summary"),
        mismatches=(state.reconciliation or {}).get("mismatches", []),
    )
    await checkpointer.save(state)
    return state, summary_record


@router.post("/summary")
async def generate_summary(payload: FilingSummaryRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    state, summary_record = await _refresh_submission_summary(state, is_final=payload.is_final)
    return {
        "thread_id": payload.thread_id,
        "submission_summary": state.submission_summary,
        "pending_submission": state.pending_submission,
        "submission_status": state.submission_status,
        "summary_record": summary_record,
    }


@router.post("/submit/prepare")
async def prepare_submit(payload: SubmitPrepareRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "prepare_submit")
    if not state.submission_summary or not state.pending_submission:
        state, _ = await _refresh_submission_summary(state, is_final=payload.is_final)

    if not state.pending_submission:
        raise HTTPException(status_code=409, detail="blocking_issues_prevent_submission")

    state.pending_submission["is_final"] = payload.is_final
    result = await approval_gate.approval_gate(state)
    state.apply_update(result)
    state.submission_status = "awaiting_submission_approval"
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "submission_summary": state.submission_summary,
        "pending_approvals": state.pending_approvals,
        "submission_status": state.submission_status,
    }


@router.post("/submit/complete")
async def complete_submit(payload: CompleteSubmissionRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "complete_submit")
    if not await filing_runtime.has_approved_kind(thread_id=payload.thread_id, kinds=["submit_final", "submit_draft"]):
        raise HTTPException(status_code=409, detail="submission_approval_required")
    if not state.submission_summary:
        raise HTTPException(status_code=409, detail="submission_summary_required")

    artifacts = await filing_runtime.archive_submission_artifacts(
        thread_id=payload.thread_id,
        assessment_year=state.submission_summary.get("assessment_year", state.tax_facts.get("assessment_year", "2025-26")),
        itr_type=state.submission_summary.get("itr_type", state.itr_type),
        tax_facts=state.tax_facts,
        fact_evidence=state.fact_evidence,
        reconciliation=state.reconciliation,
        submission_summary=state.submission_summary,
        summary_markdown=_latest_node_message(state, "submission_summary"),
        ack_no=payload.ack_no,
        portal_ref=payload.portal_ref,
        filed_at=payload.filed_at,
        itrv_text=payload.itr_v_text,
    )

    state.pending_submission = None
    state.submission_status = "submitted"
    state.filing_artifacts = artifacts
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "submission_status": state.submission_status,
        "artifacts": artifacts,
    }


@router.post("/artifacts/official")
async def attach_official_artifact(payload: OfficialArtifactAttachmentRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    if state.submission_status not in {"submitted", "verified"} and not state.filing_artifacts:
        raise HTTPException(status_code=409, detail="submission_artifacts_required")

    try:
        prepared = prepare_official_artifact_attachment(
            artifact_kind=payload.artifact_kind,
            page_type=payload.page_type,
            page_title=payload.page_title,
            page_url=payload.page_url,
            portal_state=payload.portal_state,
            manual_text=payload.manual_text,
            ack_no=payload.ack_no,
            portal_ref=payload.portal_ref,
            filed_at=payload.filed_at,
        )
        prepared["metadata"]["assessment_year"] = state.submission_summary.get(
            "assessment_year", state.tax_facts.get("assessment_year")
        )
        artifacts = await filing_runtime.attach_official_artifact(
            thread_id=payload.thread_id,
            artifact_kind=prepared["artifact_kind"],
            content=prepared["content"],
            ack_no=prepared.get("ack_no"),
            portal_ref=prepared.get("portal_ref"),
            filed_at=prepared.get("filed_at"),
            metadata=prepared["metadata"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="filed_artifacts_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state.filing_artifacts = artifacts
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "artifacts": artifacts,
        "official_artifact": {
            "artifact_kind": prepared["artifact_kind"],
            "ack_no": prepared.get("ack_no"),
            "portal_ref": prepared.get("portal_ref"),
            "filed_at": prepared.get("filed_at"),
        },
    }


@router.post("/everify/prepare")
async def prepare_everify(payload: EVerifyPrepareRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "prepare_everify")
    if state.submission_status != "submitted":
        raise HTTPException(status_code=409, detail="submission_must_be_completed_first")

    state.pending_everify = {"method": payload.method}
    result = await approval_gate.approval_gate(state)
    state.apply_update(result)
    state.submission_status = "awaiting_everify_approval"
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "pending_approvals": state.pending_approvals,
        "submission_status": state.submission_status,
        "pending_everify": state.pending_everify,
    }


@router.post("/everify/start")
async def start_everify(payload: EVerifyStartRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "start_everify")
    if not await filing_runtime.has_approved_kind(thread_id=payload.thread_id, kinds=["everify"]):
        raise HTTPException(status_code=409, detail="everify_approval_required")

    method = payload.method or (state.pending_everify or {}).get("method")
    if not method:
        raise HTTPException(status_code=400, detail="everify_method_required")

    state.everify_method = method
    result = await everify_handoff.everify_handoff(state)
    state.apply_update(result)
    state.pending_everify = None
    state.submission_status = "verification_in_progress"
    everify_record = await filing_runtime.start_everification(
        thread_id=payload.thread_id,
        assessment_year=state.submission_summary.get("assessment_year", state.tax_facts.get("assessment_year", "2025-26")),
        handoff=state.everify_handoff or {},
    )
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "submission_status": state.submission_status,
        "everify_handoff": state.everify_handoff,
        "everification": everify_record,
        "pending_navigation": state.get("pending_navigation"),
    }


@router.post("/everify/complete")
async def complete_everify(payload: EVerifyCompleteRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "complete_everify")
    assessment_year = state.submission_summary.get("assessment_year", state.tax_facts.get("assessment_year", "2025-26"))
    try:
        everify_record = await filing_runtime.complete_everification(
            thread_id=payload.thread_id,
            assessment_year=assessment_year,
            handoff_id=payload.handoff_id,
            portal_ref=payload.portal_ref,
            verified_at=payload.verified_at,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="everify_handoff_not_found") from exc

    if state.everify_handoff:
        state.everify_handoff["status"] = "completed"
        state.everify_handoff["portal_ref"] = payload.portal_ref
    state.submission_status = "verified"
    state.awaiting_verification_complete = False
    state.user_in_control = False
    state = await archive.run(state)
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "submission_status": state.submission_status,
        "everification": everify_record,
        "archived": state.archived,
    }


@router.post("/revision")
async def create_revision(payload: RevisionCreateRequest) -> dict[str, Any]:
    base_state = await require_thread_state(payload.thread_id)
    prior_return = {
        "thread_id": base_state.thread_id,
        "tax_facts": base_state.tax_facts,
        "submission_summary": base_state.submission_summary,
        "filing_artifacts": base_state.filing_artifacts,
        "submission_status": base_state.submission_status,
    }

    revision_seed = AgentState(
        thread_id=base_state.thread_id,
        user_id=base_state.user_id,
        itr_type=base_state.itr_type,
        current_page=base_state.current_page,
        portal_page=base_state.portal_page,
        tax_facts=base_state.tax_facts,
        fact_evidence=base_state.fact_evidence,
        reconciliation=base_state.reconciliation,
        documents=base_state.documents,
        messages=list(base_state.messages),
    )
    revision_seed.revision_request = {
        "prior_return": prior_return,
        "revision_number": payload.revision_number,
        "reason": payload.reason,
    }

    updates = await revised_return.revised_return(revision_seed)
    revision_thread_id = updates.get("thread_id")
    if not revision_thread_id:
        raise HTTPException(status_code=500, detail="revision_thread_not_created")

    revision_state = AgentState(
        thread_id=revision_thread_id,
        user_id=base_state.user_id,
        itr_type=base_state.itr_type,
        current_node="bootstrap",
        current_page=base_state.current_page,
        portal_page=base_state.portal_page,
        tax_facts=updates.get("tax_facts", base_state.tax_facts),
        fact_evidence=base_state.fact_evidence,
        reconciliation=base_state.reconciliation,
        documents=base_state.documents,
        messages=updates.get("messages", []),
        revision_context=updates.get("revision_context", {}),
    )
    await checkpointer.save(revision_state)
    await filing_runtime.record_revision_branch(
        base_thread_id=base_state.thread_id,
        revision_thread_id=revision_thread_id,
        revision_number=payload.revision_number,
        reason=payload.reason,
        prior_return=prior_return,
    )
    return {
        "base_thread_id": base_state.thread_id,
        "revision_thread_id": revision_thread_id,
        "revision_context": revision_state.revision_context,
    }


@router.post("/consents/revoke")
async def revoke_consent(payload: ConsentRevokeRequest) -> dict[str, Any]:
    await require_thread_state(payload.thread_id)
    auth = get_request_auth(required=True)
    try:
        revoked = await retention_service.revoke_consent_and_queue_purge(
            consent_id=payload.consent_id,
            thread_id=payload.thread_id,
            requested_by=auth.user_id,
            reason=payload.reason,
            process_immediately=payload.process_immediately,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="consent_not_found") from exc
    return revoked


@router.post("/regime-preview")
async def regime_preview(payload: RegimePreviewRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    if not state.tax_facts:
        raise HTTPException(status_code=409, detail="tax_facts_required")
    return {
        "thread_id": payload.thread_id,
        **compare_regimes(state.tax_facts),
    }


@router.post("/year-over-year")
async def year_over_year(payload: YearOverYearRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    if not state.submission_summary:
        state, _ = await _refresh_submission_summary(state, is_final=True)
    prior_state = select_prior_filed_state(state, await checkpointer.list_latest_states())
    comparison = build_year_over_year_comparison(state, prior_state)
    return await filing_runtime.record_year_over_year_comparison(
        thread_id=payload.thread_id,
        user_id=state.user_id,
        current_assessment_year=assessment_year_for_state(state),
        prior_thread_id=prior_state.thread_id if prior_state else None,
        prior_assessment_year=assessment_year_for_state(prior_state) if prior_state else None,
        comparison=comparison,
    )


@router.post("/next-ay-checklist")
async def next_ay_checklist(payload: NextAyChecklistRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    if not state.submission_summary:
        state, _ = await _refresh_submission_summary(state, is_final=True)
    checklist = build_next_ay_checklist(state)
    return await filing_runtime.upsert_next_ay_checklist(
        thread_id=payload.thread_id,
        user_id=state.user_id,
        current_assessment_year=checklist.get("current_assessment_year"),
        target_assessment_year=str(checklist.get("target_assessment_year")),
        checklist=checklist.get("items", []),
        summary=checklist.get("summary", {}),
    )


@router.post("/notices/prepare")
async def prepare_notice(payload: NoticePreparationRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    prepared = prepare_notice_response(state, payload.notice_text, payload.notice_type)
    extracted = {key: value for key, value in prepared.items() if key not in {"explanation_md", "suggested_response"}}
    return await filing_runtime.record_notice_preparation(
        thread_id=payload.thread_id,
        user_id=state.user_id,
        notice_type=payload.notice_type,
        assessment_year=prepared.get("assessment_year"),
        notice_text=payload.notice_text,
        extracted=extracted,
        explanation_md=prepared["explanation_md"],
        suggested_response=prepared["suggested_response"],
    )


@router.post("/refund-status/capture")
async def capture_refund_status(payload: RefundStatusCaptureRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    try:
        snapshot = build_refund_status_capture(
            state,
            page_type=payload.page_type,
            page_title=payload.page_title,
            page_url=payload.page_url,
            portal_state=payload.portal_state,
            manual_status=payload.manual_status,
            manual_portal_ref=payload.manual_portal_ref,
            manual_refund_amount=payload.manual_refund_amount,
            manual_issued_at=payload.manual_issued_at,
            manual_processed_at=payload.manual_processed_at,
            manual_refund_mode=payload.manual_refund_mode,
            manual_bank_masked=payload.manual_bank_masked,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await filing_runtime.record_refund_status(
        thread_id=payload.thread_id,
        user_id=state.user_id,
        assessment_year=snapshot.get("assessment_year"),
        status=str(snapshot["status"]),
        refund_amount=snapshot.get("refund_amount"),
        portal_ref=snapshot.get("portal_ref"),
        issued_at=snapshot.get("issued_at"),
        processed_at=snapshot.get("processed_at"),
        refund_mode=snapshot.get("refund_mode"),
        bank_masked=snapshot.get("bank_masked"),
        source=str(snapshot["source"]),
        observation=snapshot.get("observation", {}),
    )


@router.get("/{thread_id}")
async def filing_state(thread_id: str) -> dict[str, Any]:
    state = await require_thread_state(thread_id)
    return {
        "thread_id": thread_id,
        "submission_status": state.submission_status,
        "submission_summary": state.submission_summary,
        "pending_submission": state.pending_submission,
        "pending_everify": state.pending_everify,
        "everify_handoff": state.everify_handoff,
        "artifacts": await filing_runtime.latest_artifacts(thread_id),
        "summary_record": await filing_runtime.latest_submission_summary(thread_id),
        "everification": await filing_runtime.latest_everification(thread_id),
        "consents": await filing_runtime.list_consents(thread_id),
        "purge_jobs": await retention_service.list_purge_jobs(thread_id),
        "revision": await filing_runtime.latest_revision(thread_id),
        "year_over_year": await filing_runtime.latest_year_over_year(thread_id),
        "next_ay_checklist": await filing_runtime.latest_next_ay_checklist(thread_id),
        "notices": await filing_runtime.list_notice_preparations(thread_id),
        "refund_status": await filing_runtime.latest_refund_status(thread_id),
        "archived": state.archived,
    }


@router.get("/{thread_id}/artifacts/{artifact_name}")
async def download_artifact(thread_id: str, artifact_name: str) -> Response:
    await require_thread_state(thread_id)
    artifacts = await filing_runtime.latest_artifacts(thread_id)
    if not artifacts:
        raise HTTPException(status_code=404, detail="filed_artifacts_not_found")

    artifact_map = {
        "itr-v": artifacts.get("itr_v_storage_uri"),
        "offline-json": artifacts.get("json_export_uri"),
        "evidence-bundle": artifacts.get("evidence_bundle_uri"),
        "summary": artifacts.get("summary_storage_uri"),
    }
    storage_uri = artifact_map.get(artifact_name)
    if not storage_uri:
        raise HTTPException(status_code=404, detail="artifact_not_found")

    content, media_type = filing_runtime.read_artifact(storage_uri)
    filename = storage_uri.split("/")[-1]
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )