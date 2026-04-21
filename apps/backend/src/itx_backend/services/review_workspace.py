from __future__ import annotations

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
    async def support_assessment(self, thread_id: str) -> dict[str, Any]:
        state = await checkpointer.latest(thread_id)
        if state is None:
            raise KeyError(thread_id)
        activity = await action_runtime.list_thread_activity(thread_id)
        assessment = assess_agent_state(state, activity)
        assessment["handoffs"] = await self.list_handoffs(thread_id)
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


review_workspace = ReviewWorkspaceService()