from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
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


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _archive_member_name(storage_uri: str, prefix: str) -> str:
    filename = storage_uri.split("/")[-1]
    return f"{prefix}/{filename}"


_RESOLUTION_OPEN = "open"
_RESOLUTION_RESOLVED = "resolved"
VERDICT_RESOLUTION_STATUSES = {"open", "acknowledged", "resolved"}


def _mismatch_item_id(mismatch: dict[str, Any], index: int) -> str:
    raw_id = mismatch.get("id") or mismatch.get("mismatch_id")
    if raw_id:
        return str(raw_id)
    field = str(mismatch.get("field") or mismatch.get("label") or "mismatch")
    source = str(mismatch.get("source") or mismatch.get("category") or "ais")
    return f"{source}:{field}:{index}"


def _document_item_id(doc: dict[str, Any], index: int) -> str:
    return str(doc.get("document_id") or doc.get("id") or f"doc:{index}")


def _resolution_index(state: AgentState) -> dict[tuple[str, str], dict[str, Any]]:
    reconciliation = state.reconciliation or {}
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in reconciliation.get("resolutions", []) or []:
        code = str(entry.get("code") or "")
        item_id = str(entry.get("item_id") or "")
        if code and item_id:
            index[(code, item_id)] = entry
    return index


def _evidence_item(
    *,
    item_id: str,
    summary: str,
    code: str,
    resolutions: dict[tuple[str, str], dict[str, Any]],
    severity: Optional[str] = None,
    ref: Optional[dict[str, Any]] = None,
    actions: Optional[list[dict[str, Any]]] = None,
    detail: Optional[Any] = None,
    resolvable: bool = True,
) -> dict[str, Any]:
    resolution = resolutions.get((code, item_id))
    status = str(resolution.get("status")) if resolution else _RESOLUTION_OPEN
    return {
        "id": item_id,
        "code": code,
        "summary": summary,
        "severity": severity or "medium",
        "ref": ref or {},
        "detail": detail,
        "status": status,
        "resolvable": resolvable and status != _RESOLUTION_RESOLVED,
        "resolution": resolution,
        "actions": actions
        or [
            {"id": "resolve", "label": "Mark resolved", "kind": "resolve", "requires_approval": False},
            {"id": "acknowledge", "label": "Acknowledge", "kind": "acknowledge", "requires_approval": False},
        ],
    }


def _has_real_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return abs(float(value)) > 0.005
    if isinstance(value, str):
        return value.strip() not in {"", "0", "0.0", "None", "null"}
    return True


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _mismatch_sides(mismatch: dict[str, Any]) -> tuple[Any, Any]:
    """Return (ais_side_value, doc_side_value) using the canonical reconcile keys."""
    ais_value = mismatch.get("ais_value", mismatch.get("expected"))
    # reconcile emits both `our_value` and `doc_value`; prefer an explicit document-side key
    doc_value = mismatch.get("doc_value")
    if doc_value is None:
        doc_value = mismatch.get("our_value", mismatch.get("document_value", mismatch.get("actual")))
    return ais_value, doc_value


def _material_mismatch_evidence(
    mismatches: list[dict[str, Any]],
    resolutions: dict[tuple[str, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (open_material_evidence, all_material_evidence).

    Skips mismatches where neither side has a real value — those are "no data yet", not a
    discrepancy, and should not block filing. Per-item actions are filtered to only the
    ones that make sense: e.g. Accept AIS is hidden when AIS has no value.
    """
    all_items: list[dict[str, Any]] = []
    for index, mismatch in enumerate(mismatches):
        severity = str(mismatch.get("severity", "")).lower()
        if severity not in {"error", "high", "warning"}:
            continue

        ais_value, doc_value = _mismatch_sides(mismatch)
        ais_has = _has_real_value(ais_value)
        doc_has = _has_real_value(doc_value)
        if not ais_has and not doc_has:
            # Both sides empty: nothing to reconcile. Skip entirely.
            continue

        item_id = _mismatch_item_id(mismatch, index)
        field = mismatch.get("field") or mismatch.get("label") or "field"
        category = mismatch.get("category") or "mismatch"
        summary = (
            f"{field}: AIS {_format_value(ais_value)} vs document {_format_value(doc_value)}"
            f" ({category.replace('_', ' ').replace('-', ' ')})"
        )

        actions: list[dict[str, Any]] = []
        if ais_has:
            actions.append(
                {
                    "id": "accept_ais",
                    "label": "Accept AIS value",
                    "kind": "accept_ais",
                    "requires_approval": False,
                    "value": ais_value,
                }
            )
        if doc_has:
            actions.append(
                {
                    "id": "accept_doc",
                    "label": "Accept document value",
                    "kind": "accept_doc",
                    "requires_approval": False,
                    "value": doc_value,
                }
            )
        actions.append(
            {
                "id": "note",
                "label": "Add note",
                "kind": "note",
                "requires_approval": False,
                "prompts_for_note": True,
            }
        )
        actions.append(
            {"id": "resolve", "label": "Mark reviewed", "kind": "resolve", "requires_approval": False}
        )

        all_items.append(
            _evidence_item(
                item_id=item_id,
                summary=summary,
                code="material-mismatches",
                resolutions=resolutions,
                severity=severity,
                ref={
                    "field": field,
                    "category": category,
                    "document_id": mismatch.get("document_id"),
                    "ais_value": ais_value,
                    "doc_value": doc_value,
                },
                actions=actions,
                detail=mismatch,
            )
        )
    open_items = [item for item in all_items if item["status"] != _RESOLUTION_RESOLVED]
    return open_items, all_items


def _flagged_document_evidence(
    documents: list[dict[str, Any]],
    resolutions: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, doc in enumerate(documents):
        risk = str(((doc.get("security") or {}).get("prompt_injection_risk") or "")).lower()
        if risk not in {"medium", "high"}:
            continue
        item_id = _document_item_id(doc, index)
        name = doc.get("file_name") or doc.get("name") or item_id
        evidence.append(
            _evidence_item(
                item_id=item_id,
                summary=f"{name} flagged for prompt-injection risk ({risk}).",
                code="document-security",
                resolutions=resolutions,
                severity=risk,
                ref={"document_id": item_id, "doc_type": doc.get("doc_type")},
                actions=[
                    {"id": "override", "label": "Override with justification", "kind": "override", "requires_approval": True},
                    {"id": "resolve", "label": "Mark reviewed", "kind": "resolve", "requires_approval": False},
                    {"id": "quarantine", "label": "Quarantine document", "kind": "quarantine", "requires_approval": False},
                ],
                detail={"risk": risk, "security": doc.get("security")},
            )
        )
    return evidence


def _capital_gains_evidence(
    capital_gains: dict[str, Any],
    resolutions: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    keys = ("derivatives", "futures_options", "intraday", "crypto")
    for key in keys:
        value = capital_gains.get(key)
        if not _truthy(value):
            continue
        count = value if isinstance(value, (int, float)) else None
        summary = f"{key.replace('_', ' ').title()} activity present" + (f" ({count} entries)" if count else "")
        evidence.append(
            _evidence_item(
                item_id=key,
                summary=summary,
                code="complex-capital-gains",
                resolutions=resolutions,
                severity="high",
                ref={"field": f"capital_gains.{key}"},
                detail=value,
            )
        )
    return evidence


def _directorship_evidence(
    tax_facts: dict[str, Any],
    resolutions: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    raw = tax_facts.get("directorship")
    if not _truthy(raw):
        return []
    entries: list[dict[str, Any]]
    if isinstance(raw, list):
        entries = [entry for entry in raw if isinstance(entry, dict)]
    elif isinstance(raw, dict):
        entries = [raw]
    else:
        entries = [{"summary": str(raw)}]
    evidence: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        company = entry.get("company") or entry.get("name") or f"entry-{index}"
        din = entry.get("din") or entry.get("DIN")
        summary = f"Directorship at {company}" + (f" (DIN {din})" if din else "")
        evidence.append(
            _evidence_item(
                item_id=str(entry.get("din") or entry.get("id") or f"directorship-{index}"),
                summary=summary,
                code="directorship",
                resolutions=resolutions,
                severity="high",
                ref={"field": "directorship", "company": company, "din": din},
                detail=entry,
            )
        )
    return evidence


def _blocking_issue_evidence(
    blocking_issues: list[Any],
    resolutions: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, issue in enumerate(blocking_issues):
        text = str(issue)
        evidence.append(
            _evidence_item(
                item_id=f"blocker-{index}",
                summary=text,
                code="submission-blocker",
                resolutions=resolutions,
                severity="high",
                ref={"index": index, "text": text},
            )
        )
    return evidence


def _quarantine_trail(security_status: dict[str, Any]) -> list[dict[str, Any]]:
    trail = security_status.get("trail") or security_status.get("history") or []
    result: list[dict[str, Any]] = []
    if isinstance(trail, list):
        for entry in trail[-5:]:
            if isinstance(entry, dict):
                result.append(
                    {
                        "actor": entry.get("actor", "system"),
                        "verb": entry.get("verb", "anomaly"),
                        "at": entry.get("at") or entry.get("timestamp"),
                        "note": entry.get("note") or entry.get("reason"),
                    }
                )
    return result


def assess_agent_state(state: AgentState, activity: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    tax_facts = state.tax_facts or {}
    documents = state.documents or []
    rejected_documents = state.rejected_documents or []
    reconciliation = state.reconciliation or {}
    mismatches = reconciliation.get("mismatches", [])
    blocking_issues = (state.submission_summary or {}).get("blocking_issues", [])
    approvals = (activity or {}).get("approvals", [])
    security_status = current_quarantine_status(state)
    resolutions_index = _resolution_index(state)

    reasons: list[dict[str, Any]] = []
    checklist: list[str] = []

    if security_status.get("quarantined"):
        reasons.append(
            {
                "code": "thread-quarantined",
                "title": "Automation is quarantined for this thread",
                "detail": f"{security_status.get('reason') or 'Anomaly detection paused automation until you resume it manually.'}",
                "severity": "medium",
                "evidence": [],
                "actions": [
                    {"id": "resume", "label": "Resume automation", "kind": "resume_quarantine", "requires_approval": True},
                    {"id": "view_anomalies", "label": "View anomalies", "kind": "open_security", "requires_approval": False},
                ],
                "trail": _quarantine_trail(security_status),
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
                "evidence": [
                    _evidence_item(
                        item_id="foreign-assets-declared",
                        summary="Foreign assets flag set on tax facts — Schedule FA needed.",
                        code="foreign-assets",
                        resolutions=resolutions_index,
                        severity="high",
                        ref={"field": "tax_facts.foreign_assets"},
                        detail=tax_facts.get("foreign_assets"),
                    )
                ],
                "actions": [
                    {"id": "handoff", "label": "Prepare CA handoff", "kind": "prepare_handoff", "requires_approval": False},
                    {"id": "open_tax_facts", "label": "Open tax facts", "kind": "open_tax_facts", "requires_approval": False},
                ],
                "trail": [],
            }
        )
        checklist.extend(
            [
                "Collect foreign account, asset, and income statements for the assessment year.",
                "Review Schedule FA and foreign-tax-credit requirements with a CA before submission.",
            ]
        )

    capital_gains = tax_facts.get("capital_gains") or {}
    if isinstance(capital_gains, dict):
        cg_evidence = _capital_gains_evidence(capital_gains, resolutions_index)
        if cg_evidence:
            reasons.append(
                {
                    "code": "complex-capital-gains",
                    "title": "Complex capital-gains activity detected",
                    "detail": "Derivatives, intraday, or crypto trades need manual schedule validation before filing.",
                    "severity": "high",
                    "evidence": cg_evidence,
                    "actions": [
                        {"id": "open_capital_gains", "label": "Open capital gains", "kind": "open_capital_gains", "requires_approval": False},
                    ],
                    "trail": [],
                }
            )
            checklist.append("Export broker contract notes and a realized-P&L statement for CA review.")

    directorship_evidence = _directorship_evidence(tax_facts, resolutions_index)
    if directorship_evidence:
        reasons.append(
            {
                "code": "directorship",
                "title": "Director disclosure needs review",
                "detail": "Director or unlisted-shareholding disclosures are not safe to autofill without reviewer confirmation.",
                "severity": "high",
                "evidence": directorship_evidence,
                "actions": [
                    {"id": "open_tax_facts", "label": "Open tax facts", "kind": "open_tax_facts", "requires_approval": False},
                ],
                "trail": [],
            }
        )
        checklist.append("Confirm directorship, DIN, and unlisted-shareholding disclosures with a reviewer.")

    material_mismatches_open, material_mismatches_all = _material_mismatch_evidence(mismatches, resolutions_index)
    if len(material_mismatches_open) >= 2:
        reasons.append(
            {
                "code": "material-mismatches",
                "title": "Multiple material mismatches remain unresolved",
                "detail": f"{len(material_mismatches_open)} mismatches still need manual confirmation against source documents.",
                "severity": "medium",
                "evidence": material_mismatches_all,
                "actions": [
                    {"id": "reconcile", "label": "Open reconciliation", "kind": "open_reconciliation", "requires_approval": False},
                ],
                "trail": [],
            }
        )
        checklist.append("Resolve AIS-vs-document mismatches before allowing another fill or submit step.")

    flagged_evidence = _flagged_document_evidence([*documents, *rejected_documents], resolutions_index)
    if flagged_evidence:
        highest_risk = "high" if any(item["severity"] == "high" and item["status"] != _RESOLUTION_RESOLVED for item in flagged_evidence) else "medium"
        reasons.append(
            {
                "code": "document-security",
                "title": "Risky document content was flagged",
                "detail": "Uploaded text contained prompt-like instructions or suspicious control text and should be reviewed manually.",
                "severity": highest_risk,
                "evidence": flagged_evidence,
                "actions": [
                    {"id": "open_documents", "label": "Open documents", "kind": "open_documents", "requires_approval": False},
                ],
                "trail": [],
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
                "evidence": _blocking_issue_evidence(blocking_issues, resolutions_index),
                "actions": [
                    {"id": "open_submission", "label": "Open submission summary", "kind": "open_submission", "requires_approval": False},
                ],
                "trail": [],
            }
        )
        checklist.append("Review filing blockers with a CA before attempting submission again.")

    mode_trigger: Optional[str] = None
    if reasons:
        high_reasons = [reason for reason in reasons if reason["severity"] == "high"]
        if high_reasons:
            mode = "ca-handoff"
            mode_trigger = high_reasons[0]["code"]
        else:
            mode = "guided-checklist"
            mode_trigger = reasons[0]["code"]
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
        "mode_trigger": mode_trigger,
        "can_autofill": can_autofill,
        "can_submit": can_submit,
        "reason_count": len(reasons),
        "reasons": reasons,
        "checklist": list(dict.fromkeys(checklist)),
        "blocking_issues": blocking_issues,
        "mismatch_count": len(material_mismatches_open),
        "mismatch_total": len(material_mismatches_all),
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

    async def verdicts(self, thread_id: str) -> dict[str, Any]:
        """Projection of assess_agent_state in VEA (verdict / evidence / action) shape."""
        assessment = await self.support_assessment(thread_id)
        verdicts = []
        for reason in assessment.get("reasons", []) or []:
            verdicts.append(
                {
                    "verdict": {
                        "code": reason.get("code"),
                        "title": reason.get("title"),
                        "detail": reason.get("detail"),
                        "severity": reason.get("severity"),
                        "mode_impact": assessment.get("mode"),
                        "is_mode_trigger": reason.get("code") == assessment.get("mode_trigger"),
                    },
                    "evidence": reason.get("evidence", []) or [],
                    "actions": reason.get("actions", []) or [],
                    "trail": reason.get("trail", []) or [],
                }
            )
        return {
            "thread_id": thread_id,
            "mode": assessment.get("mode"),
            "mode_trigger": assessment.get("mode_trigger"),
            "can_autofill": assessment.get("can_autofill"),
            "can_submit": assessment.get("can_submit"),
            "checklist": assessment.get("checklist", []),
            "verdicts": verdicts,
        }

    async def record_verdict_resolution(
        self,
        *,
        thread_id: str,
        code: str,
        item_id: str,
        status: str,
        actor_email: str,
        actor_user_id: str,
        note: Optional[str] = None,
        action_kind: Optional[str] = None,
    ) -> dict[str, Any]:
        if status not in VERDICT_RESOLUTION_STATUSES:
            raise ValueError(f"invalid status {status!r}")
        state = await checkpointer.latest(thread_id)
        if state is None:
            raise KeyError(thread_id)

        reconciliation = dict(state.reconciliation or {})
        resolutions = list(reconciliation.get("resolutions") or [])
        now_iso = datetime.now(timezone.utc).isoformat()
        filtered = [
            entry
            for entry in resolutions
            if not (str(entry.get("code")) == code and str(entry.get("item_id")) == item_id)
        ]
        entry = {
            "code": code,
            "item_id": item_id,
            "status": status,
            "note": note,
            "action_kind": action_kind,
            "actor_email": actor_email,
            "actor_user_id": actor_user_id,
            "at": now_iso,
        }
        filtered.append(entry)
        reconciliation["resolutions"] = filtered
        state.reconciliation = reconciliation
        await checkpointer.save(state)
        return {"thread_id": thread_id, "resolution": entry, "verdicts": (await self.verdicts(thread_id))["verdicts"]}

    async def build_client_export_bundle(
        self,
        *,
        thread_id: str,
        user_id: str,
        email: str,
    ) -> tuple[bytes, str]:
        state, access_role = await self.get_accessible_state(thread_id=thread_id, user_id=user_id, email=email)
        payload = await self._build_export_payload(state=state, access_role=access_role)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"client-export-{thread_id}-{timestamp}.zip"
        return self._render_export_archive(payloads=[payload], export_scope="single", filename=filename)

    async def build_bulk_export_bundle(
        self,
        *,
        user_id: str,
        email: str,
        thread_ids: Optional[list[str]] = None,
    ) -> tuple[bytes, str]:
        accessible_states = await self.list_accessible_states(user_id=user_id, email=email)
        accessible_map = {state.thread_id: (state, access_role) for state, access_role in accessible_states}

        if thread_ids:
            missing = [thread_id for thread_id in thread_ids if thread_id not in accessible_map]
            if missing:
                raise PermissionError(
                    f"export_threads_forbidden:{','.join(sorted(dict.fromkeys(missing)))}"
                )
            selected_thread_ids = list(dict.fromkeys(thread_ids))
        else:
            selected_thread_ids = [state.thread_id for state, _ in accessible_states]

        if not selected_thread_ids:
            raise ValueError("no_accessible_threads")

        payloads: list[dict[str, Any]] = []
        for thread_id in selected_thread_ids:
            state, access_role = accessible_map[thread_id]
            payloads.append(await self._build_export_payload(state=state, access_role=access_role))

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"review-workspace-export-{timestamp}.zip"
        return self._render_export_archive(payloads=payloads, export_scope="bulk", filename=filename)

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

    async def _build_export_payload(self, *, state: AgentState, access_role: str) -> dict[str, Any]:
        thread_id = state.thread_id
        activity = await action_runtime.list_thread_activity(thread_id)
        support_assessment = assess_agent_state(state, activity)
        handoffs = await self.list_handoffs(thread_id)
        signoffs = await self.list_signoffs(thread_id)
        shares = await self.list_access_grants(thread_id=thread_id)
        filing_state = {
            "submission_summary": await filing_runtime.latest_submission_summary(thread_id),
            "artifacts": await filing_runtime.latest_artifacts(thread_id),
            "everification": await filing_runtime.latest_everification(thread_id),
            "revision": await filing_runtime.latest_revision(thread_id),
            "consents": await filing_runtime.list_consents(thread_id),
            "year_over_year": await filing_runtime.latest_year_over_year(thread_id),
            "next_ay_checklist": await filing_runtime.latest_next_ay_checklist(thread_id),
            "notices": await filing_runtime.list_notice_preparations(thread_id),
            "refund_status": await filing_runtime.latest_refund_status(thread_id),
        }

        assets: list[dict[str, str]] = []
        artifacts = filing_state.get("artifacts") or {}
        for storage_uri in [
            artifacts.get("summary_storage_uri"),
            artifacts.get("json_export_uri"),
            artifacts.get("evidence_bundle_uri"),
            artifacts.get("itr_v_storage_uri"),
        ]:
            if storage_uri:
                assets.append(
                    {
                        "storage_uri": str(storage_uri),
                        "archive_path": _archive_member_name(str(storage_uri), "artifacts"),
                        "kind": "filing_artifact",
                    }
                )

        for handoff in handoffs:
            storage_uri = handoff.get("package_storage_uri")
            if storage_uri:
                assets.append(
                    {
                        "storage_uri": str(storage_uri),
                        "archive_path": _archive_member_name(str(storage_uri), "handoffs"),
                        "kind": "handoff_package",
                    }
                )

        return {
            "thread_id": thread_id,
            "access_role": access_role,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "taxpayer": {
                "name": (state.tax_facts or {}).get("name"),
                "pan": (state.tax_facts or {}).get("pan"),
            },
            "itr_type": state.itr_type,
            "submission_status": state.submission_status,
            "support_assessment": support_assessment,
            "documents": _json_safe(state.documents),
            "rejected_documents": _json_safe(state.rejected_documents),
            "tax_facts": _json_safe(state.tax_facts),
            "fact_evidence": _json_safe(state.fact_evidence),
            "reconciliation": _json_safe(state.reconciliation),
            "pending_approvals": _json_safe(state.pending_approvals),
            "messages": _json_safe(state.messages[-25:]),
            "actions": _json_safe(activity),
            "handoffs": _json_safe(handoffs),
            "reviewer_signoffs": _json_safe(signoffs),
            "shares": _json_safe(shares),
            "filing_state": _json_safe(filing_state),
            "included_assets": assets,
        }

    def _render_export_archive(
        self,
        *,
        payloads: list[dict[str, Any]],
        export_scope: str,
        filename: str,
    ) -> tuple[bytes, str]:
        created_at = datetime.now(timezone.utc).isoformat()
        manifest = {
            "created_at": created_at,
            "scope": export_scope,
            "thread_count": len(payloads),
            "threads": [payload["thread_id"] for payload in payloads],
            "missing_assets": [],
        }

        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for payload in payloads:
                thread_prefix = payload["thread_id"]
                bundle.writestr(
                    f"{thread_prefix}/client-summary.json",
                    json.dumps(payload, sort_keys=True, indent=2),
                )
                for asset in payload.get("included_assets", []):
                    storage_uri = asset.get("storage_uri")
                    archive_path = asset.get("archive_path")
                    if not storage_uri or not archive_path:
                        continue
                    try:
                        content = document_storage.read(storage_uri)
                    except FileNotFoundError:
                        manifest["missing_assets"].append(
                            {
                                "thread_id": payload["thread_id"],
                                "storage_uri": storage_uri,
                                "archive_path": archive_path,
                            }
                        )
                        continue
                    bundle.writestr(f"{thread_prefix}/{archive_path}", content)
            bundle.writestr("export-manifest.json", json.dumps(manifest, sort_keys=True, indent=2))

        return archive_bytes.getvalue(), filename

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