from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from asyncpg import Record

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.db.session import get_pool
from itx_backend.security.quarantine import current_quarantine_status
from itx_backend.services.action_runtime import action_runtime
from itx_backend.services.document_storage import document_storage
from itx_backend.services.filing_runtime import filing_runtime


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none", "null", "n"}
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return bool(value)


def assess_agent_state(state: AgentState, activity: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    tax_facts = state.tax_facts or {}
    documents = state.documents or []
    rejected_documents = state.rejected_documents or []
    reconciliation = state.reconciliation or {}
    mismatches = reconciliation.get("mismatches", [])
    blocking_issues = (state.submission_summary or {}).get("blocking_issues", [])
    approvals = (activity or {}).get("approvals", [])
    security_status = current_quarantine_status(state)

    reasons: list[dict[str, str]] = []
    checklist: list[str] = []

    if security_status.get("quarantined"):
        reasons.append(
            {
                "code": "thread-quarantined",
                "title": "Automation is quarantined for this thread",
                "detail": f"{security_status.get('reason') or 'Anomaly detection paused automation until you resume it manually.'}",
                "severity": "medium",
            }
        )
        checklist.append("Review the recent anomaly and explicitly resume the thread before more automation.")

    if _truthy(tax_facts.get("foreign_assets")):
        reasons.append(
            {
                "code": "foreign-assets",
                "title": "Foreign assets need specialist review",
                "detail": "Schedule FA and related disclosures are outside the assisted filing path.",
                "severity": "high",
            }
        )
        checklist.extend(
            [
                "Collect foreign account, asset, and income statements for the assessment year.",
                "Review Schedule FA and foreign-tax-credit requirements with a CA before submission.",
            ]
        )

    capital_gains = tax_facts.get("capital_gains") or {}
    if isinstance(capital_gains, dict) and any(
        _truthy(capital_gains.get(key)) for key in ("derivatives", "futures_options", "intraday", "crypto")
    ):
        reasons.append(
            {
                "code": "complex-capital-gains",
                "title": "Complex capital-gains activity detected",
                "detail": "Derivatives, intraday, or crypto trades need manual schedule validation before filing.",
                "severity": "high",
            }
        )
        checklist.append("Export broker contract notes and a realized-P&L statement for CA review.")

    if _truthy(tax_facts.get("directorship")):
        reasons.append(
            {
                "code": "directorship",
                "title": "Director disclosure needs review",
                "detail": "Director or unlisted-shareholding disclosures are not safe to autofill without reviewer confirmation.",
                "severity": "high",
            }
        )
        checklist.append("Confirm directorship, DIN, and unlisted-shareholding disclosures with a reviewer.")

    material_mismatches = [
        mismatch
        for mismatch in mismatches
        if str(mismatch.get("severity", "")).lower() in {"error", "high", "warning"}
    ]
    if len(material_mismatches) >= 2:
        reasons.append(
            {
                "code": "material-mismatches",
                "title": "Multiple material mismatches remain unresolved",
                "detail": f"{len(material_mismatches)} mismatches still need manual confirmation against source documents.",
                "severity": "medium",
            }
        )
        checklist.append("Resolve AIS-vs-document mismatches before allowing another fill or submit step.")

    flagged_documents = [
        doc
        for doc in [*documents, *rejected_documents]
        if str(((doc.get("security") or {}).get("prompt_injection_risk") or "")).lower() in {"medium", "high"}
    ]
    if flagged_documents:
        highest_risk = "high" if any((doc.get("security") or {}).get("prompt_injection_risk") == "high" for doc in flagged_documents) else "medium"
        reasons.append(
            {
                "code": "document-security",
                "title": "Risky document content was flagged",
                "detail": "Uploaded text contained prompt-like instructions or suspicious control text and should be reviewed manually.",
                "severity": highest_risk,
            }
        )
        checklist.append("Inspect flagged documents and confirm only factual values are being used for filing.")

    if any("Foreign assets" in str(issue) for issue in blocking_issues):
        reasons.append(
            {
                "code": "submission-blocker",
                "title": "Submission blockers require manual intervention",
                "detail": "The filing summary already reports blockers that the assisted flow should not override automatically.",
                "severity": "high",
            }
        )
        checklist.append("Review filing blockers with a CA before attempting submission again.")

    if reasons:
        mode = "ca-handoff" if any(reason["severity"] == "high" for reason in reasons) else "guided-checklist"
    else:
        mode = "supported"

    can_autofill = mode == "supported"
    can_submit = mode == "supported" and len(blocking_issues) == 0

    if mode == "supported":
        checklist.append("Continue with assisted autofill and review approvals before execution.")
    elif mode == "guided-checklist":
        checklist.append("Continue only in guided checklist mode until the flagged items are resolved.")
    else:
        checklist.append("Prepare a CA handoff package and stop automated fill or submit actions for this thread.")

    return {
        "thread_id": state.thread_id,
        "mode": mode,
        "can_autofill": can_autofill,
        "can_submit": can_submit,
        "reason_count": len(reasons),
        "reasons": reasons,
        "checklist": list(dict.fromkeys(checklist)),
        "blocking_issues": blocking_issues,
        "mismatch_count": len(material_mismatches),
        "pending_approval_count": len([approval for approval in approvals if approval.get("status") == "pending"]),
        "security_status": security_status,
    }


class ReviewWorkspaceService:
    async def _claim_active_review_access(self, *, reviewer_email: str, reviewer_user_id: str, thread_id: Optional[str] = None) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            if thread_id is None:
                await connection.execute(
                    """
                    update review_access_grants
                    set reviewer_user_id = $1,
                        accepted_at = coalesce(accepted_at, now())
                    where reviewer_email = $2 and status = 'active'
                    """,
                    reviewer_user_id,
                    _normalize_email(reviewer_email),
                )
            else:
                await connection.execute(
                    """
                    update review_access_grants
                    set reviewer_user_id = $1,
                        accepted_at = coalesce(accepted_at, now())
                    where thread_id = $2 and reviewer_email = $3 and status = 'active'
                    """,
                    reviewer_user_id,
                    thread_id,
                    _normalize_email(reviewer_email),
                )

    async def _shared_thread_ids_for_actor(self, *, reviewer_email: str, reviewer_user_id: str) -> list[str]:
        await self._claim_active_review_access(reviewer_email=reviewer_email, reviewer_user_id=reviewer_user_id)
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select thread_id
                from review_access_grants
                where reviewer_email = $1 and status = 'active'
                order by created_at desc
                """,
                _normalize_email(reviewer_email),
            )
        return [row["thread_id"] for row in rows]

    async def list_accessible_states(self, *, user_id: str, email: str) -> list[tuple[AgentState, str]]:
        latest_states = await checkpointer.list_latest_states()
        shared_thread_ids = set(await self._shared_thread_ids_for_actor(reviewer_email=email, reviewer_user_id=user_id))
        accessible: list[tuple[AgentState, str]] = []
        seen: set[str] = set()
        for state in latest_states:
            if state.user_id == user_id:
                accessible.append((state, "owner"))
                seen.add(state.thread_id)
        for thread_id in shared_thread_ids:
            if thread_id in seen:
                continue
            state = await checkpointer.latest(thread_id)
            if state is not None:
                accessible.append((state, "reviewer"))
                seen.add(thread_id)
        return accessible

    async def get_accessible_state(self, *, thread_id: str, user_id: str, email: str) -> tuple[AgentState, str]:
        state = await checkpointer.latest(thread_id)
        if state is None:
            raise KeyError(thread_id)
        if state.user_id == user_id:
            return state, "owner"

        shared_thread_ids = set(await self._shared_thread_ids_for_actor(reviewer_email=email, reviewer_user_id=user_id))
        if thread_id in shared_thread_ids:
            await self._claim_active_review_access(reviewer_email=email, reviewer_user_id=user_id, thread_id=thread_id)
            return state, "reviewer"

        raise PermissionError(thread_id)

    async def grant_reviewer_access(
        self,
        *,
        thread_id: str,
        owner_user_id: str,
        reviewer_email: str,
        scope: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        grant_id = uuid.uuid4()
        normalized_email = _normalize_email(reviewer_email)
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into review_access_grants (
                    id, thread_id, owner_user_id, reviewer_email, status, scope
                )
                values ($1, $2, $3, $4, 'active', $5::jsonb)
                on conflict (thread_id, reviewer_email) do update
                set status = 'active',
                    owner_user_id = excluded.owner_user_id,
                    scope = excluded.scope,
                    revoked_at = null
                """,
                grant_id,
                thread_id,
                owner_user_id,
                normalized_email,
                json.dumps(scope or {}, sort_keys=True),
            )
        return await self.get_access_grant(thread_id=thread_id, reviewer_email=normalized_email)

    async def get_access_grant(self, *, thread_id: str, reviewer_email: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, owner_user_id, reviewer_email, reviewer_user_id,
                       status, scope::text as scope, created_at, accepted_at, revoked_at
                from review_access_grants
                where thread_id = $1 and reviewer_email = $2
                """,
                thread_id,
                _normalize_email(reviewer_email),
            )
        if row is None:
            raise KeyError(thread_id)
        return self._serialize_access_grant(row)

    async def list_access_grants(self, *, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, thread_id, owner_user_id, reviewer_email, reviewer_user_id,
                       status, scope::text as scope, created_at, accepted_at, revoked_at
                from review_access_grants
                where thread_id = $1
                order by created_at desc
                """,
                thread_id,
            )
        return [self._serialize_access_grant(row) for row in rows]

    async def support_assessment(self, thread_id: str) -> dict[str, Any]:
        state = await checkpointer.latest(thread_id)
        if state is None:
            raise KeyError(thread_id)
        activity = await action_runtime.list_thread_activity(thread_id)
        assessment = assess_agent_state(state, activity)
        assessment["handoffs"] = await self.list_handoffs(thread_id)
        assessment["reviewer_signoffs"] = await self.list_signoffs(thread_id)
        return assessment

    async def prepare_handoff(
        self,
        *,
        thread_id: str,
        requested_by_user_id: str,
        requested_by_email: str,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        state = await checkpointer.latest(thread_id)
        if state is None:
            raise KeyError(thread_id)

        activity = await action_runtime.list_thread_activity(thread_id)
        assessment = assess_agent_state(state, activity)
        handoff_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        storage_uri = f"review-handoffs/{thread_id}/{handoff_id}.json"

        package_payload = {
            "handoff_id": handoff_id,
            "thread_id": thread_id,
            "created_at": created_at,
            "requested_by": {
                "user_id": requested_by_user_id,
                "email": requested_by_email,
            },
            "reason": reason or "unsupported_or_guided_case",
            "support_assessment": assessment,
            "taxpayer": {
                "name": state.tax_facts.get("name"),
                "pan": state.tax_facts.get("pan"),
            },
            "itr_type": state.itr_type,
            "submission_summary": state.submission_summary,
            "documents": [
                {
                    "id": doc.get("id"),
                    "name": doc.get("name"),
                    "type": doc.get("type"),
                    "status": doc.get("status"),
                    "security": doc.get("security", {}),
                }
                for doc in state.documents
            ],
            "rejected_documents": state.rejected_documents,
            "recent_messages": state.messages[-10:],
            "pending_approvals": [
                approval for approval in activity.get("approvals", []) if approval.get("status") == "pending"
            ],
            "recent_executions": activity.get("executions", [])[:5],
            "reconciliation": state.reconciliation,
        }
        document_storage.write(
            storage_uri,
            json.dumps(package_payload, sort_keys=True, indent=2).encode("utf-8"),
        )

        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into review_handoffs (
                    id, thread_id, requested_by_user_id, support_mode, status,
                    reason, reasons_json, checklist_json, summary_json, package_storage_uri
                )
                values ($1, $2, $3, $4, 'prepared', $5, $6::jsonb, $7::jsonb, $8::jsonb, $9)
                """,
                uuid.UUID(handoff_id),
                thread_id,
                requested_by_user_id,
                assessment["mode"],
                reason,
                json.dumps(assessment["reasons"], sort_keys=True),
                json.dumps(assessment["checklist"], sort_keys=True),
                json.dumps(package_payload, sort_keys=True),
                storage_uri,
            )

        return await self.get_handoff(thread_id, handoff_id)

    async def request_signoff(
        self,
        *,
        thread_id: str,
        approval_key: str,
        owner_user_id: str,
        reviewer_email: str,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_email = _normalize_email(reviewer_email)
        pool = await get_pool()
        async with pool.acquire() as connection:
            approval = await connection.fetchrow(
                """
                select approval_key, proposal_id, kind, description, status
                from approvals
                where thread_id = $1 and approval_key = $2
                """,
                thread_id,
                approval_key,
            )
            if approval is None:
                raise KeyError(approval_key)

        await self.grant_reviewer_access(
            thread_id=thread_id,
            owner_user_id=owner_user_id,
            reviewer_email=normalized_email,
            scope={
                "thread_id": thread_id,
                "approval_key": approval_key,
                "proposal_id": str(approval["proposal_id"]) if approval["proposal_id"] else None,
                "kind": approval["kind"],
            },
        )

        signoff_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into reviewer_signoffs (
                    id, thread_id, approval_key, proposal_id, owner_user_id,
                    reviewer_email, status, request_note, details_json
                )
                values ($1, $2, $3, $4, $5, $6, 'pending_reviewer', $7, $8::jsonb)
                on conflict (approval_key) do update
                set reviewer_email = excluded.reviewer_email,
                    status = 'pending_reviewer',
                    request_note = excluded.request_note,
                    reviewer_note = null,
                    client_note = null,
                    reviewer_user_id = null,
                    reviewed_at = null,
                    client_decided_at = null,
                    client_consent_key = null,
                    details_json = excluded.details_json
                """,
                signoff_id,
                thread_id,
                approval_key,
                approval["proposal_id"],
                owner_user_id,
                normalized_email,
                note,
                json.dumps(
                    {
                        "approval_kind": approval["kind"],
                        "approval_description": approval["description"],
                        "approval_status": approval["status"],
                    },
                    sort_keys=True,
                ),
            )
        return await self.get_signoff_by_approval_key(thread_id=thread_id, approval_key=approval_key)

    async def reviewer_decision(
        self,
        *,
        signoff_id: str,
        reviewer_user_id: str,
        reviewer_email: str,
        approved: bool,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_email = _normalize_email(reviewer_email)
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                update reviewer_signoffs
                set reviewer_user_id = $2,
                    status = $3,
                    reviewer_note = $4,
                    reviewed_at = now()
                where id = $1::uuid and reviewer_email = $5
                returning thread_id, approval_key
                """,
                signoff_id,
                reviewer_user_id,
                "reviewer_approved" if approved else "reviewer_rejected",
                note,
                normalized_email,
            )
        if row is None:
            raise KeyError(signoff_id)
        await self._claim_active_review_access(reviewer_email=normalized_email, reviewer_user_id=reviewer_user_id, thread_id=row["thread_id"])
        return await self.get_signoff_by_approval_key(thread_id=row["thread_id"], approval_key=row["approval_key"])

    async def client_counter_consent(
        self,
        *,
        signoff_id: str,
        owner_user_id: str,
        approved: bool,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        consent_key = f"reviewer-signoff:{signoff_id}"
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select thread_id, approval_key, reviewer_email, details_json::text as details_json, status
                from reviewer_signoffs
                where id = $1::uuid and owner_user_id = $2
                """,
                signoff_id,
                owner_user_id,
            )
        if row is None:
            raise KeyError(signoff_id)
        if row["status"] != "reviewer_approved":
            raise ValueError("reviewer_signoff_not_ready")

        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                update reviewer_signoffs
                set status = $2,
                    client_note = $3,
                    client_decided_at = now(),
                    client_consent_key = $4
                where id = $1::uuid
                """,
                signoff_id,
                "client_approved" if approved else "client_rejected",
                note,
                consent_key,
            )

        if approved:
            consent_text = (
                f"I counter-consent to reviewer sign-off for approval {row['approval_key']} "
                f"reviewed by {row['reviewer_email']}."
            )
            response_hash = hashlib.sha256(
                json.dumps(
                    {
                        "signoff_id": signoff_id,
                        "approved": True,
                        "owner_user_id": owner_user_id,
                        "note": note,
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            await filing_runtime.record_consent(
                thread_id=row["thread_id"],
                user_id=owner_user_id,
                purpose="reviewer_counter_consent",
                approval_key=consent_key,
                scope={
                    "signoff_id": signoff_id,
                    "approval_key": row["approval_key"],
                    "reviewer_email": row["reviewer_email"],
                    "details": json.loads(row["details_json"] or "{}"),
                },
                consent_text=consent_text,
                response_hash=response_hash,
                granted_at=datetime.now(timezone.utc).isoformat(),
            )

        return await self.get_signoff(thread_id=row["thread_id"], signoff_id=signoff_id)

    async def list_signoffs(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select rs.id, rs.thread_id, rs.approval_key, rs.proposal_id,
                       rs.owner_user_id, rs.reviewer_email, rs.reviewer_user_id,
                       rs.status, rs.request_note, rs.reviewer_note, rs.client_note,
                       rs.client_consent_key, rs.details_json::text as details_json,
                       rs.created_at, rs.reviewed_at, rs.client_decided_at,
                       a.kind as approval_kind, a.description as approval_description, a.status as approval_status
                from reviewer_signoffs rs
                left join approvals a on a.approval_key = rs.approval_key
                where rs.thread_id = $1
                order by rs.created_at desc
                """,
                thread_id,
            )
        return [self._serialize_signoff(row) for row in rows]

    async def get_signoff(self, *, thread_id: str, signoff_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select rs.id, rs.thread_id, rs.approval_key, rs.proposal_id,
                       rs.owner_user_id, rs.reviewer_email, rs.reviewer_user_id,
                       rs.status, rs.request_note, rs.reviewer_note, rs.client_note,
                       rs.client_consent_key, rs.details_json::text as details_json,
                       rs.created_at, rs.reviewed_at, rs.client_decided_at,
                       a.kind as approval_kind, a.description as approval_description, a.status as approval_status
                from reviewer_signoffs rs
                left join approvals a on a.approval_key = rs.approval_key
                where rs.thread_id = $1 and rs.id = $2::uuid
                """,
                thread_id,
                signoff_id,
            )
        if row is None:
            raise KeyError(signoff_id)
        return self._serialize_signoff(row)

    async def get_signoff_by_approval_key(self, *, thread_id: str, approval_key: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select rs.id, rs.thread_id, rs.approval_key, rs.proposal_id,
                       rs.owner_user_id, rs.reviewer_email, rs.reviewer_user_id,
                       rs.status, rs.request_note, rs.reviewer_note, rs.client_note,
                       rs.client_consent_key, rs.details_json::text as details_json,
                       rs.created_at, rs.reviewed_at, rs.client_decided_at,
                       a.kind as approval_kind, a.description as approval_description, a.status as approval_status
                from reviewer_signoffs rs
                left join approvals a on a.approval_key = rs.approval_key
                where rs.thread_id = $1 and rs.approval_key = $2
                """,
                thread_id,
                approval_key,
            )
        if row is None:
            raise KeyError(approval_key)
        return self._serialize_signoff(row)

    async def list_handoffs(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, thread_id, requested_by_user_id, support_mode, status, reason,
                       reasons_json::text as reasons_json,
                       checklist_json::text as checklist_json,
                       summary_json::text as summary_json,
                       package_storage_uri, created_at, updated_at
                from review_handoffs
                where thread_id = $1
                order by created_at desc
                """,
                thread_id,
            )
        return [self._serialize_handoff(row) for row in rows]

    async def get_handoff(self, thread_id: str, handoff_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, requested_by_user_id, support_mode, status, reason,
                       reasons_json::text as reasons_json,
                       checklist_json::text as checklist_json,
                       summary_json::text as summary_json,
                       package_storage_uri, created_at, updated_at
                from review_handoffs
                where thread_id = $1 and id = $2::uuid
                """,
                thread_id,
                handoff_id,
            )
        if row is None:
            raise KeyError(handoff_id)
        return self._serialize_handoff(row)

    async def read_handoff_package(self, thread_id: str, handoff_id: str) -> tuple[bytes, str, str]:
        handoff = await self.get_handoff(thread_id, handoff_id)
        storage_uri = handoff.get("package_storage_uri")
        if not storage_uri:
            raise KeyError(handoff_id)
        content = document_storage.read(str(storage_uri))
        return content, "application/json", str(storage_uri).split("/")[-1]

    def _serialize_handoff(self, row: Record) -> dict[str, Any]:
        return {
            "handoff_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "requested_by_user_id": row["requested_by_user_id"],
            "support_mode": row["support_mode"],
            "status": row["status"],
            "reason": row["reason"],
            "reasons": json.loads(row["reasons_json"] or "[]"),
            "checklist": json.loads(row["checklist_json"] or "[]"),
            "summary": json.loads(row["summary_json"] or "{}"),
            "package_storage_uri": row["package_storage_uri"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    def _serialize_access_grant(self, row: Record) -> dict[str, Any]:
        return {
            "grant_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "owner_user_id": row["owner_user_id"],
            "reviewer_email": row["reviewer_email"],
            "reviewer_user_id": row["reviewer_user_id"],
            "status": row["status"],
            "scope": json.loads(row["scope"] or "{}"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "accepted_at": row["accepted_at"].isoformat() if row["accepted_at"] else None,
            "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
        }

    def _serialize_signoff(self, row: Record) -> dict[str, Any]:
        return {
            "signoff_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "approval_key": row["approval_key"],
            "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
            "owner_user_id": row["owner_user_id"],
            "reviewer_email": row["reviewer_email"],
            "reviewer_user_id": row["reviewer_user_id"],
            "status": row["status"],
            "request_note": row["request_note"],
            "reviewer_note": row["reviewer_note"],
            "client_note": row["client_note"],
            "client_consent_key": row["client_consent_key"],
            "details": json.loads(row["details_json"] or "{}"),
            "approval_kind": row["approval_kind"],
            "approval_description": row["approval_description"],
            "approval_status": row["approval_status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
            "client_decided_at": row["client_decided_at"].isoformat() if row["client_decided_at"] else None,
        }


review_workspace = ReviewWorkspaceService()