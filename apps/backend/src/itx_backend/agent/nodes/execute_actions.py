from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from itx_backend.agent.state import AgentState
from itx_backend.services.action_runtime import action_runtime


def _collect_required_action_ids(fill_plan: dict) -> list[str]:
    return [
        action.get("action_id")
        for page in fill_plan.get("pages", [])
        for action in page.get("actions", [])
        if action.get("requires_approval", True)
    ]


def _find_selector_failure(executed: list[dict], blocked: list[dict]) -> Optional[dict]:
    for item in blocked + executed:
        if item.get("result") in {"selector_miss", "readback_mismatch", "validation_error"}:
            return {
                "field_id": item.get("field_id"),
                "field_label": item.get("field_label"),
                "page_type": item.get("page_type", "unknown"),
                "selector": item.get("selector"),
                "error_type": item.get("result") or item.get("reason") or "unknown_error",
            }
    return None


async def run(state: AgentState) -> AgentState:
    fill_plan = state.get("fill_plan", {})
    approved_actions = set(state.get("approved_actions", []))
    proposal_id = state.get("action_proposal_id")
    browser_execution = state.get("browser_execution") or {}
    portal_state = deepcopy(state.get("portal_state", {}) or {})
    portal_fields = portal_state.setdefault("fields", {})
    validation_errors = portal_state.get("validationErrors", [])
    executed = []
    blocked = []
    observed_validation_errors = []
    selector_failure = None

    required_action_ids = _collect_required_action_ids(fill_plan)

    if proposal_id and required_action_ids:
        has_approval = await action_runtime.proposal_has_approved_action_ids(proposal_id, required_action_ids)
        if not has_approval:
            blocked = [
                {
                    **action,
                    "reason": "missing_durable_approval",
                }
                for page in fill_plan.get("pages", [])
                for action in page.get("actions", [])
            ]
            state.apply_update(
                {
                    "blocked_actions": blocked,
                    "executed_actions": [],
                    "validation_summary": {
                        "executed": 0,
                        "blocked": len(blocked),
                        "readback_failures": 0,
                    },
                }
            )
            return state

    if browser_execution.get("execution_results"):
        portal_state_before = deepcopy(browser_execution.get("portal_state_before") or state.get("portal_state", {}) or {})
        portal_state_after = deepcopy(browser_execution.get("portal_state_after") or portal_state_before)
        observed_validation_errors = browser_execution.get("validation_errors", []) or []

        for result in browser_execution.get("execution_results", []):
            action_id = result.get("action_id")
            if result.get("requires_approval", True) and action_id not in approved_actions:
                blocked.append({**result, "reason": "missing_approval"})
                continue

            read_after_write = result.get("read_after_write", {})
            normalized = {
                **result,
                "status": "executed",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "read_after_write": {
                    "ok": read_after_write.get("ok", False),
                    "observed_value": read_after_write.get("observed_value"),
                    "previous_value": read_after_write.get("previous_value"),
                },
            }
            if not normalized.get("result"):
                normalized["result"] = "ok" if normalized["read_after_write"].get("ok") else "readback_mismatch"
            executed.append(normalized)

        selector_failure = _find_selector_failure(executed, blocked)
        messages = state.get("messages", [])
        messages.append(
            {
                "role": "assistant",
                "content": f"Action execution complete: {len(executed)} executed, {len(blocked)} blocked.",
                "metadata": {"node": "execute_actions", "mode": "browser_reported"},
            }
        )

        execution_id = await action_runtime.record_execution(
            thread_id=state.thread_id,
            proposal_id=proposal_id,
            execution_kind="fill",
            portal_state_before=portal_state_before,
            portal_state_after=portal_state_after,
            executed_actions=executed,
            blocked_actions=blocked,
            validation_errors=observed_validation_errors,
            audit_key=state.get("tax_facts", {}).get("assessment_year") or state.thread_id,
        )

        state.apply_update(
            {
                "messages": messages,
                "executed_actions": executed,
                "blocked_actions": blocked,
                "portal_state": portal_state_after,
                "last_execution_portal_state": portal_state_after,
                "validation_summary": {
                    "executed": len(executed),
                    "blocked": len(blocked),
                    "readback_failures": len([item for item in executed if item.get("result") in {"readback_mismatch", "validation_error"}]),
                },
                "selector_failure": selector_failure,
                "last_execution_id": execution_id,
                "browser_execution": None,
                "action_history": state.get("action_history", []) + [
                    {
                        "execution_id": execution_id,
                        "proposal_id": proposal_id,
                        "executed": len(executed),
                        "blocked": len(blocked),
                    }
                ],
            }
        )
        return state

    for page in fill_plan.get("pages", []):
        for action in page.get("actions", []):
            action_id = action.get("action_id")
            if action.get("requires_approval", True) and action_id not in approved_actions:
                blocked.append({**action, "reason": "missing_approval"})
                continue
            selector = action.get("selector")
            field_observation = portal_fields.get(selector)
            if field_observation is None:
                failure = {
                    **action,
                    "status": "selector_miss",
                    "result": "selector_miss",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                    "read_after_write": {"ok": False, "observed_value": None, "previous_value": None},
                }
                blocked.append({**failure, "reason": "selector_miss"})
                if selector_failure is None:
                    selector_failure = {
                        "field_id": action.get("field_id"),
                        "field_label": action.get("field_label"),
                        "page_type": page.get("page_type", "unknown"),
                        "selector": selector,
                        "error_type": "selector_miss",
                    }
                continue

            previous_value = field_observation.get("value")
            field_observation["value"] = action.get("value")
            observed_value = field_observation.get("value")
            read_ok = str(observed_value) == str(action.get("value"))

            matching_errors = [
                error
                for error in validation_errors
                if error.get("field") in {action.get("field_id"), selector, action.get("field_label")}
            ]
            if matching_errors:
                observed_validation_errors.extend(
                    {
                        "page_key": page.get("page_type"),
                        "field": error.get("field", action.get("field_id")),
                        "message": error.get("message", "Validation error"),
                        "parsed_reason": error.get("parsed_reason"),
                    }
                    for error in matching_errors
                )

            result = "ok"
            if matching_errors:
                result = "validation_error"
            elif not read_ok:
                result = "readback_mismatch"
                if selector_failure is None:
                    selector_failure = {
                        "field_id": action.get("field_id"),
                        "field_label": action.get("field_label"),
                        "page_type": page.get("page_type", "unknown"),
                        "selector": selector,
                        "error_type": "readback_mismatch",
                    }
            executed.append(
                {
                    **action,
                    "page_type": page.get("page_type"),
                    "status": "executed",
                    "result": result,
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                    "read_after_write": {
                        "ok": read_ok and not matching_errors,
                        "observed_value": observed_value,
                        "previous_value": previous_value,
                    },
                }
            )

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"Action execution complete: {len(executed)} executed, {len(blocked)} blocked.",
            "metadata": {"node": "execute_actions"},
        }
    )

    execution_id = await action_runtime.record_execution(
        thread_id=state.thread_id,
        proposal_id=proposal_id,
        execution_kind="fill",
        portal_state_before=state.get("portal_state", {}) or {},
        portal_state_after=portal_state,
        executed_actions=executed,
        blocked_actions=blocked,
        validation_errors=observed_validation_errors,
        audit_key=state.get("tax_facts", {}).get("assessment_year") or state.thread_id,
    )

    state.apply_update(
        {
            "messages": messages,
            "executed_actions": executed,
            "blocked_actions": blocked,
            "portal_state": portal_state,
            "last_execution_portal_state": portal_state,
            "validation_summary": {
                "executed": len(executed),
                "blocked": len(blocked),
                "readback_failures": len([item for item in executed if item.get("result") in {"readback_mismatch", "validation_error"}]),
            },
            "selector_failure": selector_failure,
            "last_execution_id": execution_id,
            "browser_execution": None,
            "action_history": state.get("action_history", []) + [
                {
                    "execution_id": execution_id,
                    "proposal_id": proposal_id,
                    "executed": len(executed),
                    "blocked": len(blocked),
                }
            ],
        }
    )
    return state
