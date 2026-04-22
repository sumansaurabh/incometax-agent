from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.nodes.fill_plan import FIELD_MAPPINGS, fill_plan as run_fill_plan
from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.action_runtime import action_runtime, detect_sensitivity
from itx_backend.services.portal_context import portal_context_service

logger = logging.getLogger(__name__)

_PAGE_TYPES = sorted(FIELD_MAPPINGS.keys())
_PROPOSAL_TTL_MINUTES = 30


def _portal_fields_from_snapshot(snapshot: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Reshape a flat snapshot field list into the {selector: {value, ...}} map fill_plan expects.

    The portal_snapshots row stores fields as an array of `{id, label, selector, value, ...}`.
    The fill_plan node looks up portal values by CSS selector, so we re-key here. Only the
    `value` attribute is ever read downstream; everything else is preserved for diagnostics.
    """
    if not snapshot:
        return {}
    by_selector: dict[str, Any] = {}
    for field in snapshot.get("fields") or []:
        if not isinstance(field, dict):
            continue
        selector = field.get("selector") or field.get("id") or field.get("name")
        if not selector:
            continue
        by_selector[str(selector)] = {
            "value": field.get("value"),
            "type": field.get("type"),
            "required": field.get("required"),
        }
    return by_selector


def _build_state_payload(
    *,
    thread_id: str,
    page_type: Optional[str],
    field_id: Optional[str],
    portal_snapshot: Optional[dict[str, Any]],
    tax_facts: dict[str, Any],
    fact_evidence: dict[str, Any],
) -> dict[str, Any]:
    current_page = page_type or (portal_snapshot or {}).get("page_type") or "unknown"
    portal_fields = _portal_fields_from_snapshot(portal_snapshot)
    portal_state = {
        "fields": portal_fields,
        "page": current_page,
        "url": (portal_snapshot or {}).get("current_url"),
        "validationErrors": (portal_snapshot or {}).get("errors") or [],
    }
    return {
        "thread_id": thread_id,
        "current_page": current_page,
        "tax_facts": tax_facts,
        "portal_state": portal_state,
        "fact_evidence": fact_evidence,
        "fill_target": {"page_type": page_type, "field_id": field_id} if page_type or field_id else {},
        "messages": [],
    }


class _StateAdapter:
    """Bridge the fill_plan node's `state.get(key, default)` contract against a plain dict.

    The fill_plan node is designed to run on the LangGraph AgentState. We feed it a dict whose
    shape matches AgentState.get() so we don't have to instantiate the full pydantic model just
    to run one node in isolation.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        return self._data.get(key)


@tool_registry.tool(
    name="propose_fill",
    description=(
        "Draft a form-fill proposal for one or more e-Filing portal pages based on the user's "
        "extracted tax facts and the current page state. ALWAYS returns a proposal — it NEVER "
        "executes. The proposal carries a diff card (fields to change, source document for each, "
        "confidence level) that the extension renders for the user to approve. The user must "
        "approve in the extension UI before the fill is applied to the portal. Call this when "
        "the user says 'fill this page for me', 'auto-fill my Form 16 details', 'help me fill "
        "the deductions'. If the user is not on a known page type, call get_form_schema first "
        "to inspect what's available. Each proposal is persisted with a proposal_id you can "
        "reference in later turns; the proposal expires after 30 minutes."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "page_type": {
                "type": "string",
                "enum": _PAGE_TYPES,
                "description": (
                    "Optional narrow-down. Omit to draft fills for every page where we have facts."
                ),
            },
            "field_id": {
                "type": "string",
                "description": (
                    "Optional single-field narrow-down. Must be used with page_type. Use when the "
                    "user asks to fill only one specific field."
                ),
            },
            "reason": {
                "type": "string",
                "description": (
                    "Short explanation of why the fill is being proposed, shown to the user on the "
                    "diff card (e.g. 'Auto-filling salary details from Form 16')."
                ),
            },
        },
        "additionalProperties": False,
    },
)
async def propose_fill(
    *,
    thread_id: str,
    page_type: Optional[str] = None,
    field_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    # Snapshot + facts.
    snapshot = await portal_context_service.get(thread_id)
    agent_state = await checkpointer.latest(thread_id)
    if agent_state is None:
        return {
            "error": "no_tax_facts",
            "hint": (
                "No extracted facts are available for this thread yet. Ask the user to upload "
                "their Form 16 / AIS / other tax documents first."
            ),
        }

    tax_facts = agent_state.get("tax_facts", {}) or {}
    if not tax_facts:
        return {
            "error": "no_tax_facts",
            "hint": "Tax facts have not been extracted from uploaded documents yet.",
        }

    fact_evidence = agent_state.get("fact_evidence", {}) or {}

    state_payload = _build_state_payload(
        thread_id=thread_id,
        page_type=page_type,
        field_id=field_id,
        portal_snapshot=snapshot,
        tax_facts=tax_facts,
        fact_evidence=fact_evidence,
    )

    try:
        result = await run_fill_plan(_StateAdapter(state_payload))
    except Exception as exc:  # noqa: BLE001 — planner failure must not crash the turn
        logger.exception("propose_fill.plan_failed")
        return {"error": f"plan_failed:{type(exc).__name__}:{exc}"}

    plan = result.get("fill_plan") or {}
    total_actions = int(plan.get("total_actions", 0))

    if total_actions == 0:
        return {
            "proposal_id": None,
            "status": "nothing_to_fill",
            "message": (
                "No fillable differences found between your extracted facts and the current portal "
                "page. Either the page is already filled, or we do not yet have facts for it."
            ),
            "plan": plan,
        }

    sensitivity = detect_sensitivity(plan)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=_PROPOSAL_TTL_MINUTES)).isoformat()
    try:
        proposal_id = await action_runtime.create_proposal(
            thread_id=thread_id,
            proposal_type="fill",
            dsl=plan,
            reason=reason or "auto_generated_fill_plan",
            sensitivity=sensitivity,
            expires_at=expires_at,
        )
    except Exception as exc:  # noqa: BLE001 — persistence failure should surface as tool error
        logger.exception("propose_fill.persist_failed")
        return {"error": f"persist_failed:{type(exc).__name__}:{exc}"}

    action_ids = [
        action.get("action_id")
        for page in plan.get("pages", [])
        for action in page.get("actions", [])
        if action.get("action_id")
    ]

    # Also create a pending approval row keyed by proposal_id so the extension has a single
    # approval surface rather than having to infer one from proposal fields.
    try:
        await action_runtime.create_approval(
            thread_id=thread_id,
            proposal_id=proposal_id,
            kind="fill",
            approval_key=f"fill:{proposal_id}",
            description=reason or f"Fill {total_actions} field(s)",
            consent_text=f"Apply {total_actions} field(s) to the portal from your uploaded documents.",
            action_ids=action_ids,
            expires_at=expires_at,
        )
    except Exception as exc:  # noqa: BLE001 — approval row is nice-to-have; proposal is the source of truth
        logger.warning("propose_fill.approval_row_failed", extra={"proposal_id": proposal_id, "error": str(exc)})

    return {
        "proposal_id": proposal_id,
        "status": "awaiting_approval",
        "sensitivity": sensitivity,
        "expires_at": expires_at,
        "total_actions": total_actions,
        "high_confidence_actions": plan.get("high_confidence_actions"),
        "low_confidence_actions": plan.get("low_confidence_actions"),
        "pages": plan.get("pages", []),
        "approval_key": f"fill:{proposal_id}",
        "message": (
            f"Drafted a {total_actions}-field fill proposal. The user must approve in the "
            "extension side panel before any field is touched."
        ),
    }
