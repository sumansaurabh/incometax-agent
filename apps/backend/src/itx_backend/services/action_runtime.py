from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from asyncpg import Record

from itx_backend.db.session import get_pool


RULE_VERSION = "phase3-fill-1"
DEFAULT_ADAPTER_VERSION = "phase3-static-adapter"


@dataclass
class PersistedApproval:
    proposal_id: str
    approval_id: str


def clone_portal_state(portal_state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(portal_state or {})


def filter_fill_plan(fill_plan: dict[str, Any], page_type: Optional[str] = None, field_id: Optional[str] = None) -> dict[str, Any]:
    pages = []
    for page in fill_plan.get("pages", []):
        if page_type and page.get("page_type") != page_type:
            continue
        actions = []
        for action in page.get("actions", []):
            if field_id and action.get("field_id") != field_id:
                continue
            actions.append(action)
        if actions:
            pages.append({**page, "actions": actions})

    total_actions = sum(len(page.get("actions", [])) for page in pages)
    high_conf = sum(
        1
        for page in pages
        for action in page.get("actions", [])
        if action.get("confidence_level") == "high"
    )
    low_conf = sum(
        1
        for page in pages
        for action in page.get("actions", [])
        if action.get("confidence_level") == "low"
    )
    return {
        **fill_plan,
        "pages": pages,
        "total_actions": total_actions,
        "high_confidence_actions": high_conf,
        "low_confidence_actions": low_conf,
    }


def detect_sensitivity(fill_plan: dict[str, Any]) -> str:
    field_ids = [
        action.get("field_id", "")
        for page in fill_plan.get("pages", [])
        for action in page.get("actions", [])
    ]
    if any(field_id.startswith("bank.") for field_id in field_ids):
        return "high"
    if any("regime" in field_id for field_id in field_ids):
        return "high"
    if len(field_ids) == 1:
        return "focused"
    return "standard"


def _normalize_timestamp(value: Optional[Any]) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported timestamp value: {type(value)!r}")


class ActionRuntimeService:
    async def create_proposal(
        self,
        *,
        thread_id: str,
        proposal_type: str,
        dsl: dict[str, Any],
        reason: str,
        sensitivity: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> str:
        proposal_id = str(uuid.uuid4())
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into action_proposals (id, thread_id, proposal_type, dsl, sensitivity, reason, expires_at)
                values ($1, $2, $3, $4::jsonb, $5, $6, $7)
                """,
                uuid.UUID(proposal_id),
                thread_id,
                proposal_type,
                json.dumps(dsl, sort_keys=True),
                sensitivity,
                reason,
                _normalize_timestamp(expires_at),
            )
        return proposal_id

    async def create_approval(
        self,
        *,
        thread_id: str,
        proposal_id: Optional[str],
        kind: str,
        approval_key: str,
        description: str,
        consent_text: str,
        action_ids: list[str],
        expires_at: Optional[str],
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into approvals (
                    id, thread_id, kind, proposal_id, approval_key, description,
                    consent_text, status, action_ids, expires_at
                )
                values ($1, $2, $3, $4, $5, $6, $7, 'pending', $8::jsonb, $9)
                on conflict (approval_key) do update
                set description = excluded.description,
                    consent_text = excluded.consent_text,
                    kind = excluded.kind,
                    proposal_id = excluded.proposal_id,
                    action_ids = excluded.action_ids,
                    expires_at = excluded.expires_at,
                    status = 'pending'
                """,
                uuid.uuid4(),
                thread_id,
                kind,
                uuid.UUID(proposal_id) if proposal_id else None,
                approval_key,
                description,
                consent_text,
                json.dumps(action_ids),
                _normalize_timestamp(expires_at),
            )

    async def record_approval_decision(
        self,
        *,
        approval_key: str,
        approved: bool,
        response_hash: str,
        rejection_reason: Optional[str],
        decision_payload: Optional[dict[str, Any]],
    ) -> Optional[PersistedApproval]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                update approvals
                set status = $2,
                    user_decision = $3,
                    decided_at = now(),
                    response_hash = $4,
                    rejection_reason = $5,
                    decision_payload = $6::jsonb
                where approval_key = $1
                returning proposal_id, approval_key
                """,
                approval_key,
                "approved" if approved else "rejected",
                "approved" if approved else "rejected",
                response_hash,
                rejection_reason,
                json.dumps(decision_payload or {}, sort_keys=True),
            )
        if not row:
            return None
        return PersistedApproval(
            proposal_id=str(row["proposal_id"]) if row["proposal_id"] else "",
            approval_id=row["approval_key"],
        )

    async def proposal_has_approved_action_ids(self, proposal_id: str, action_ids: list[str]) -> bool:
        if not proposal_id or not action_ids:
            return False
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select action_ids::text as action_ids
                from approvals
                where proposal_id = $1 and status = 'approved'
                """,
                uuid.UUID(proposal_id),
            )
        approved_action_ids = set()
        for row in rows:
            approved_action_ids.update(json.loads(row["action_ids"] or "[]"))
        return all(action_id in approved_action_ids for action_id in action_ids)

    async def record_execution(
        self,
        *,
        thread_id: str,
        proposal_id: Optional[str],
        execution_kind: str,
        portal_state_before: dict[str, Any],
        portal_state_after: dict[str, Any],
        executed_actions: list[dict[str, Any]],
        blocked_actions: list[dict[str, Any]],
        validation_errors: list[dict[str, Any]],
        audit_key: str,
    ) -> str:
        execution_id = str(uuid.uuid4())
        success = len(executed_actions) > 0 and all(action.get("result") == "ok" for action in executed_actions)
        result_payload = {
            "executed_actions": executed_actions,
            "blocked_actions": blocked_actions,
            "validation_errors": validation_errors,
        }
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into action_executions (
                        id, proposal_id, thread_id, execution_kind, ended_at,
                        success, error, portal_state_before, portal_state_after, results_json
                    )
                    values ($1, $2, $3, $4, now(), $5, $6, $7::jsonb, $8::jsonb, $9::jsonb)
                    """,
                    uuid.UUID(execution_id),
                    uuid.UUID(proposal_id) if proposal_id else None,
                    thread_id,
                    execution_kind,
                    success,
                    None if success else "execution_contains_failures",
                    json.dumps(portal_state_before, sort_keys=True),
                    json.dumps(portal_state_after, sort_keys=True),
                    json.dumps(result_payload, sort_keys=True),
                )

                for action in executed_actions:
                    readback = action.get("read_after_write", {})
                    await connection.execute(
                        """
                        insert into field_fill_history (
                            id, thread_id, proposal_id, execution_id, page_key,
                            field_id, field_label, selector, value_before, value_entered,
                            observed_value, source_evidence_key, source_document,
                            rule_version, result
                        )
                        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                        """,
                        uuid.uuid4(),
                        thread_id,
                        uuid.UUID(proposal_id) if proposal_id else None,
                        uuid.UUID(execution_id),
                        action.get("page_type"),
                        action.get("field_id"),
                        action.get("field_label"),
                        action.get("selector"),
                        readback.get("previous_value") and str(readback.get("previous_value")),
                        str(action.get("value")),
                        readback.get("observed_value") and str(readback.get("observed_value")),
                        action.get("source_fact_id"),
                        action.get("source_document"),
                        RULE_VERSION,
                        action.get("result", "ok"),
                    )
                    await connection.execute(
                        """
                        insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                        values ($1, $2, $3, $4::jsonb, $5, $6)
                        """,
                        uuid.uuid4(),
                        audit_key,
                        "field_filled",
                        json.dumps(action, sort_keys=True),
                        RULE_VERSION,
                        action.get("page_type") or DEFAULT_ADAPTER_VERSION,
                    )

                for error in validation_errors:
                    await connection.execute(
                        """
                        insert into validation_errors (
                            id, thread_id, execution_id, page_key, field, message, parsed_reason
                        )
                        values ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        uuid.uuid4(),
                        thread_id,
                        uuid.UUID(execution_id),
                        error.get("page_key"),
                        error.get("field"),
                        error.get("message"),
                        error.get("parsed_reason"),
                    )
        return execution_id

    async def undo_execution(self, *, execution_id: str, portal_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select proposal_id, results_json::text as results_json
                from action_executions
                where id = $1 and thread_id = $2
                """,
                uuid.UUID(execution_id),
                thread_id,
            )
        if not row:
            raise KeyError(execution_id)

        results = json.loads(row["results_json"] or "{}")
        updated_state = clone_portal_state(portal_state)
        fields = updated_state.setdefault("fields", {})
        reverted_actions = []
        for action in reversed(results.get("executed_actions", [])):
            selector = action.get("selector")
            if not selector or selector not in fields:
                continue
            previous_value = action.get("read_after_write", {}).get("previous_value")
            fields[selector]["value"] = previous_value
            reverted_actions.append(
                {
                    "action_id": action.get("action_id"),
                    "selector": selector,
                    "restored_value": previous_value,
                }
            )

        undo_execution_id = await self.record_execution(
            thread_id=thread_id,
            proposal_id=str(row["proposal_id"]) if row["proposal_id"] else None,
            execution_kind="undo",
            portal_state_before=portal_state,
            portal_state_after=updated_state,
            executed_actions=[
                {
                    "action_id": item["action_id"],
                    "field_id": item["selector"],
                    "field_label": item["selector"],
                    "selector": item["selector"],
                    "page_type": updated_state.get("page"),
                    "value": item["restored_value"],
                    "result": "ok",
                    "read_after_write": {
                        "previous_value": item["restored_value"],
                        "observed_value": item["restored_value"],
                        "ok": True,
                    },
                }
                for item in reverted_actions
            ],
            blocked_actions=[],
            validation_errors=[],
            audit_key=thread_id,
        )
        return {
            "execution_id": undo_execution_id,
            "portal_state": updated_state,
            "reverted_actions": reverted_actions,
        }

    async def list_thread_activity(self, thread_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            proposals = await connection.fetch(
                """
                select id, proposal_type, dsl::text as dsl, sensitivity, reason, created_at, expires_at
                from action_proposals
                where thread_id = $1
                order by created_at desc
                """,
                thread_id,
            )
            approvals = await connection.fetch(
                """
                select approval_key, kind, proposal_id, description, status, action_ids::text as action_ids,
                       created_at, expires_at, decided_at, rejection_reason
                from approvals
                where thread_id = $1
                order by created_at desc
                """,
                thread_id,
            )
            executions = await connection.fetch(
                """
                select id, proposal_id, execution_kind, started_at, ended_at, success, error,
                       results_json::text as results_json
                from action_executions
                where thread_id = $1
                order by started_at desc
                """,
                thread_id,
            )
        return {
            "proposals": [self._serialize_proposal(row) for row in proposals],
            "approvals": [self._serialize_approval(row) for row in approvals],
            "executions": [self._serialize_execution(row) for row in executions],
        }

    def _serialize_proposal(self, row: Record) -> dict[str, Any]:
        return {
            "proposal_id": str(row["id"]),
            "proposal_type": row["proposal_type"],
            "dsl": json.loads(row["dsl"] or "{}"),
            "sensitivity": row["sensitivity"],
            "reason": row["reason"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        }

    def _serialize_approval(self, row: Record) -> dict[str, Any]:
        return {
            "approval_id": row["approval_key"],
            "kind": row["kind"],
            "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
            "description": row["description"],
            "status": row["status"],
            "action_ids": json.loads(row["action_ids"] or "[]"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
            "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
            "rejection_reason": row["rejection_reason"],
        }

    def _serialize_execution(self, row: Record) -> dict[str, Any]:
        return {
            "execution_id": str(row["id"]),
            "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
            "execution_kind": row["execution_kind"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "ended_at": row["ended_at"].isoformat() if row["ended_at"] else None,
            "success": row["success"],
            "error": row["error"],
            "results": json.loads(row["results_json"] or "{}"),
        }


action_runtime = ActionRuntimeService()