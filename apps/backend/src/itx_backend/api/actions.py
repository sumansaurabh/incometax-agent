from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.nodes import approval_gate, execute_actions, fill_plan, validate_response
from itx_backend.services.action_runtime import action_runtime

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ProposalRequest(BaseModel):
    thread_id: str
    page_type: Optional[str] = None
    field_id: Optional[str] = None
    portal_state: Optional[dict[str, Any]] = None


class ActionDecision(BaseModel):
    thread_id: str
    approval_id: str
    approved: bool
    consent_acknowledged: bool = True
    modifications: dict[str, Any] = Field(default_factory=dict)
    rejection_reason: Optional[str] = None


class ActionExecutionRequest(BaseModel):
    thread_id: str
    portal_state: Optional[dict[str, Any]] = None


class UndoExecutionRequest(BaseModel):
    thread_id: str
    execution_id: str
    portal_state: Optional[dict[str, Any]] = None


@router.post("/proposal")
async def proposal(payload: ProposalRequest) -> dict[str, Any]:
    state = await checkpointer.latest(payload.thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")

    state.fill_target = {
        "page_type": payload.page_type,
        "field_id": payload.field_id,
    }
    state.last_user_response = {}

    if payload.portal_state is not None:
        state.portal_state = payload.portal_state
        if payload.page_type:
            state.current_page = payload.page_type

    fill_result = await fill_plan.fill_plan(state)
    state.apply_update(
        {
            **fill_result,
        }
    )

    approval_result = await approval_gate.approval_gate(state)
    state.apply_update(approval_result)
    await checkpointer.save(state)

    return {
        "thread_id": payload.thread_id,
        "fill_plan": state.fill_plan,
        "pending_approvals": state.pending_approvals,
        "action_proposal_id": state.action_proposal_id,
    }


@router.post("/decision")
async def decision(payload: ActionDecision) -> dict[str, Any]:
    state = await checkpointer.latest(payload.thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")

    state.last_user_response = {
        "type": "approval_response",
        "approval_id": payload.approval_id,
        "approved": payload.approved,
        "consent_acknowledged": payload.consent_acknowledged,
        "modifications": payload.modifications,
        "rejection_reason": payload.rejection_reason,
    }
    result = await approval_gate.approval_gate(state)
    state.apply_update(result)
    state.last_user_response = {}
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "approval_status": result.get("approval_status"),
        "approved_actions": state.approved_actions,
        "pending_approvals": state.pending_approvals,
    }


@router.post("/execute")
async def execute(payload: ActionExecutionRequest) -> dict[str, Any]:
    state = await checkpointer.latest(payload.thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")

    if payload.portal_state is not None:
        state.portal_state = payload.portal_state

    state = await execute_actions.run(state)
    state = await validate_response.run(state)
    await checkpointer.save(state)
    return {
        "thread_id": payload.thread_id,
        "execution_id": state.last_execution_id,
        "executed_actions": state.executed_actions,
        "blocked_actions": state.blocked_actions,
        "validation_summary": state.validation_summary,
        "selector_failure": state.get("selector_failure"),
        "portal_state": state.portal_state,
    }


@router.post("/undo")
async def undo(payload: UndoExecutionRequest) -> dict[str, Any]:
    state = await checkpointer.latest(payload.thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")
    portal_state = payload.portal_state if payload.portal_state is not None else state.portal_state
    try:
        result = await action_runtime.undo_execution(
            execution_id=payload.execution_id,
            portal_state=portal_state,
            thread_id=payload.thread_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="execution_not_found") from exc
    state.portal_state = result["portal_state"]
    state.last_execution_id = result["execution_id"]
    await checkpointer.save(state)
    return result


@router.get("/thread/{thread_id}")
async def thread_actions(thread_id: str) -> dict[str, Any]:
    state = await checkpointer.latest(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="thread_not_found")
    return {
        "thread_id": thread_id,
        **(await action_runtime.list_thread_activity(thread_id)),
        "pending_approvals": state.pending_approvals,
        "approved_actions": state.approved_actions,
        "fill_plan": state.fill_plan,
    }
