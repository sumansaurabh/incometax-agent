from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.nodes import approval_gate, execute_actions, fill_plan, validate_response
from itx_backend.security.quarantine import ensure_thread_not_quarantined
from itx_backend.security.request_auth import require_thread_state
from itx_backend.services.action_runtime import action_runtime
from itx_backend.services.validation_help import translate_validation_errors

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ProposalRequest(BaseModel):
    thread_id: str
    page_type: Optional[str] = None
    field_id: Optional[str] = None
    target_value: Optional[Any] = None
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
    portal_state_before: Optional[dict[str, Any]] = None
    portal_state_after: Optional[dict[str, Any]] = None
    execution_results: list[dict[str, Any]] = Field(default_factory=list)
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)


class UndoExecutionRequest(BaseModel):
    thread_id: str
    execution_id: str
    portal_state: Optional[dict[str, Any]] = None


class ValidationHelpRequest(BaseModel):
    thread_id: str
    page_type: Optional[str] = None
    portal_state: Optional[dict[str, Any]] = None
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _set_nested_value(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


@router.post("/proposal")
async def proposal(payload: ProposalRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "proposal")
    original_value = None
    applied_override = False

    state.fill_target = {
        "page_type": payload.page_type,
        "field_id": payload.field_id,
        "target_value": payload.target_value,
    }
    state.last_user_response = {}

    if payload.portal_state is not None:
        state.portal_state = payload.portal_state
        if payload.page_type:
            state.current_page = payload.page_type

    if payload.field_id and payload.target_value is not None:
        original_value = _get_nested_value(state.tax_facts, payload.field_id)
        _set_nested_value(state.tax_facts, payload.field_id, payload.target_value)
        applied_override = True

    fill_result = await fill_plan.fill_plan(state)
    state.apply_update(
        {
            **fill_result,
        }
    )

    approval_result = await approval_gate.approval_gate(state)
    state.apply_update(approval_result)
    if applied_override and payload.field_id:
        _set_nested_value(state.tax_facts, payload.field_id, original_value)
    await checkpointer.save(state)

    return {
        "thread_id": payload.thread_id,
        "fill_plan": state.fill_plan,
        "pending_approvals": state.pending_approvals,
        "action_proposal_id": state.action_proposal_id,
    }


@router.post("/decision")
async def decision(payload: ActionDecision) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)

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
    if payload.approved and result.get("approval_status") == "approved":
        for page in state.fill_plan.get("pages", []) if state.fill_plan else []:
            for action in page.get("actions", []):
                field_id = action.get("field_id")
                if isinstance(field_id, str) and "regime" in field_id:
                    _set_nested_value(state.tax_facts, "regime", action.get("value"))
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
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "execute")

    if payload.execution_results:
        state.browser_execution = {
            "portal_state_before": payload.portal_state_before or state.portal_state,
            "portal_state_after": payload.portal_state_after or payload.portal_state or state.portal_state,
            "execution_results": payload.execution_results,
            "validation_errors": payload.validation_errors,
        }
        if payload.portal_state_before is not None:
            state.portal_state = payload.portal_state_before
    elif payload.portal_state is not None:
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
    state = await require_thread_state(payload.thread_id)
    ensure_thread_not_quarantined(state, "undo")
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


@router.post("/validation-help")
async def validation_help(payload: ValidationHelpRequest) -> dict[str, Any]:
    state = await require_thread_state(payload.thread_id)
    page_type = payload.page_type or state.current_page or (payload.portal_state or {}).get("page") or "unknown"
    portal_state = payload.portal_state or state.portal_state or {}
    validation_errors = payload.validation_errors or portal_state.get("validationErrors") or portal_state.get("validation_errors") or []
    return {
        "thread_id": payload.thread_id,
        "page_type": page_type,
        "items": translate_validation_errors(
            page_type=page_type,
            validation_errors=validation_errors,
            portal_state=portal_state,
            state=state,
        ),
    }


@router.get("/thread/{thread_id}")
async def thread_actions(thread_id: str) -> dict[str, Any]:
    state = await require_thread_state(thread_id)
    return {
        "thread_id": thread_id,
        **(await action_runtime.list_thread_activity(thread_id)),
        "pending_approvals": state.pending_approvals,
        "approved_actions": state.approved_actions,
        "fill_plan": state.fill_plan,
    }
