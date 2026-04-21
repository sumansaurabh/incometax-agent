from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from asyncpg import Record

from itx_backend.db.session import get_pool
from itx_backend.services.action_runtime import action_runtime
from itx_backend.services.document_storage import document_storage
from itx_backend.services.offline_export import offline_exporter


def _normalize_timestamp(value: Optional[Any]) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Unsupported timestamp value: {type(value)!r}")


def _json_bytes(payload: dict[str, Any] | list[Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")


def _markdown_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _artifact_storage_uri(thread_id: str, filename: str) -> str:
    return f"artifacts/{thread_id}/{filename}"


def _content_type_for_uri(storage_uri: str) -> str:
    if storage_uri.endswith(".json"):
        return "application/json"
    if storage_uri.endswith(".md"):
        return "text/markdown; charset=utf-8"
    return "text/plain; charset=utf-8"


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


class FilingRuntimeService:
    async def record_submission_summary(
        self,
        *,
        thread_id: str,
        itr_type: str,
        regime: Optional[str],
        tax_facts: dict[str, Any],
        submission_summary: dict[str, Any],
        summary_markdown: str,
        mismatches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        draft_return_id = uuid.uuid4()
        summary_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into draft_returns (id, thread_id, itr_type, regime, payload)
                    values ($1, $2, $3, $4, $5::jsonb)
                    """,
                    draft_return_id,
                    thread_id,
                    itr_type,
                    regime,
                    json.dumps(tax_facts, sort_keys=True),
                )
                await connection.execute(
                    """
                    insert into submission_summaries (
                        id, thread_id, draft_return_id, summary_json, summary_md,
                        total_income, total_deductions, taxable_income, tax_payable,
                        refund_due, mismatches
                    )
                    values ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11::jsonb)
                    """,
                    summary_id,
                    thread_id,
                    draft_return_id,
                    json.dumps(submission_summary, sort_keys=True),
                    summary_markdown,
                    submission_summary.get("gross_total_income", 0),
                    submission_summary.get("total_deductions", 0),
                    submission_summary.get("taxable_income", 0),
                    submission_summary.get("tax_payable", 0),
                    submission_summary.get("refund_due", 0),
                    json.dumps(mismatches, sort_keys=True),
                )
        return {
            "draft_return_id": str(draft_return_id),
            "summary_record_id": str(summary_id),
        }

    async def record_consent(
        self,
        *,
        thread_id: str,
        user_id: str,
        purpose: str,
        approval_key: str,
        scope: dict[str, Any],
        consent_text: str,
        response_hash: str,
        granted_at: Optional[Any],
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into consents (
                    id, thread_id, user_id, purpose, approval_key, scope,
                    granted_at, text_hash, response_hash
                )
                values ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
                on conflict (approval_key) do nothing
                """,
                uuid.uuid4(),
                thread_id,
                user_id,
                purpose,
                approval_key,
                json.dumps(scope, sort_keys=True),
                _normalize_timestamp(granted_at),
                hashlib.sha256(consent_text.encode("utf-8")).digest(),
                response_hash,
            )

    async def has_approved_kind(self, *, thread_id: str, kinds: list[str]) -> bool:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select 1
                from approvals
                where thread_id = $1
                  and kind = any($2::text[])
                  and status = 'approved'
                order by decided_at desc nulls last
                limit 1
                """,
                thread_id,
                kinds,
            )
        return row is not None

    async def archive_submission_artifacts(
        self,
        *,
        thread_id: str,
        assessment_year: str,
        itr_type: str,
        tax_facts: dict[str, Any],
        fact_evidence: dict[str, Any],
        reconciliation: dict[str, Any],
        submission_summary: dict[str, Any],
        summary_markdown: str,
        ack_no: Optional[str],
        portal_ref: Optional[str],
        filed_at: Optional[Any],
        itrv_text: Optional[str],
    ) -> dict[str, Any]:
        filed_at_value = _normalize_timestamp(filed_at) or datetime.utcnow()
        offline_json_payload = offline_exporter.export(
            tax_facts=tax_facts,
            assessment_year=assessment_year,
            itr_type=itr_type,
        )
        actions = await action_runtime.list_thread_activity(thread_id)
        evidence_bundle = {
            "thread_id": thread_id,
            "assessment_year": assessment_year,
            "tax_facts": tax_facts,
            "fact_evidence": fact_evidence,
            "reconciliation": reconciliation,
            "actions": actions,
        }
        itrv_content = itrv_text or self._render_itrv_placeholder(
            thread_id=thread_id,
            assessment_year=assessment_year,
            itr_type=itr_type,
            submission_summary=submission_summary,
            ack_no=ack_no,
            portal_ref=portal_ref,
        )

        json_export_uri = _artifact_storage_uri(thread_id, "offline-export.json")
        evidence_bundle_uri = _artifact_storage_uri(thread_id, "evidence-bundle.json")
        summary_storage_uri = _artifact_storage_uri(thread_id, "submission-summary.md")
        itrv_storage_uri = _artifact_storage_uri(thread_id, "itr-v.txt")

        document_storage.write(json_export_uri, _json_bytes(offline_json_payload))
        document_storage.write(evidence_bundle_uri, _json_bytes(evidence_bundle))
        document_storage.write(summary_storage_uri, _markdown_bytes(summary_markdown))
        document_storage.write(itrv_storage_uri, _markdown_bytes(itrv_content))

        artifact_id = uuid.uuid4()
        manifest = {
            "ack_no": ack_no,
            "portal_ref": portal_ref,
            "json_export_uri": json_export_uri,
            "evidence_bundle_uri": evidence_bundle_uri,
            "summary_storage_uri": summary_storage_uri,
            "itr_v_storage_uri": itrv_storage_uri,
            "filed_at": filed_at_value.isoformat(),
        }

        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into filed_return_artifacts (
                        id, thread_id, ack_no, itr_v_storage_uri, json_export_uri,
                        evidence_bundle_uri, summary_storage_uri, filed_at, artifact_manifest
                    )
                    values ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                    """,
                    artifact_id,
                    thread_id,
                    ack_no,
                    itrv_storage_uri,
                    json_export_uri,
                    evidence_bundle_uri,
                    summary_storage_uri,
                    filed_at_value,
                    json.dumps(manifest, sort_keys=True),
                )
                await connection.execute(
                    """
                    insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                    values ($1, $2, 'submitted', $3::jsonb, $4, $5)
                    """,
                    uuid.uuid4(),
                    assessment_year,
                    json.dumps({
                        "thread_id": thread_id,
                        "ack_no": ack_no,
                        "portal_ref": portal_ref,
                        "artifacts": manifest,
                    }, sort_keys=True),
                    "phase4-submit-1",
                    itr_type,
                )
        return {
            "artifact_id": str(artifact_id),
            **manifest,
        }

    async def attach_official_artifact(
        self,
        *,
        thread_id: str,
        artifact_kind: str,
        content: str,
        ack_no: Optional[str],
        portal_ref: Optional[str],
        filed_at: Optional[Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_kind = artifact_kind.strip().lower()
        if normalized_kind != "itr_v":
            raise ValueError("unsupported_artifact_kind")

        latest = await self.latest_artifacts(thread_id)
        if not latest:
            raise KeyError(thread_id)

        storage_uri = _artifact_storage_uri(thread_id, f"official-{normalized_kind.replace('_', '-')}.md")
        document_storage.write(storage_uri, _markdown_bytes(content))

        filed_at_value = _normalize_timestamp(filed_at)
        manifest = dict(latest.get("artifact_manifest") or {})
        previous_itrv_uri = latest.get("itr_v_storage_uri")
        if previous_itrv_uri and previous_itrv_uri != storage_uri:
            manifest.setdefault("archived_itr_v_storage_uri", previous_itrv_uri)
        manifest.update(
            {
                "ack_no": ack_no or latest.get("ack_no"),
                "portal_ref": portal_ref or manifest.get("portal_ref"),
                "official_itr_v_storage_uri": storage_uri,
                "official_artifacts": {
                    **dict(manifest.get("official_artifacts") or {}),
                    normalized_kind: {
                        "storage_uri": storage_uri,
                        "attached_at": datetime.utcnow().isoformat(),
                        "metadata": metadata,
                    },
                },
            }
        )

        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    update filed_return_artifacts
                    set ack_no = $2,
                        itr_v_storage_uri = $3,
                        filed_at = coalesce($4, filed_at),
                        artifact_manifest = $5::jsonb
                    where id = $1::uuid
                    """,
                    latest["artifact_id"],
                    ack_no or latest.get("ack_no"),
                    storage_uri,
                    filed_at_value,
                    json.dumps(manifest, sort_keys=True),
                )
                await connection.execute(
                    """
                    insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                    values ($1, $2, 'official_artifact_attached', $3::jsonb, $4, $5)
                    """,
                    uuid.uuid4(),
                    str(metadata.get("assessment_year") or "unknown"),
                    json.dumps(
                        {
                            "thread_id": thread_id,
                            "artifact_kind": normalized_kind,
                            "ack_no": ack_no or latest.get("ack_no"),
                            "portal_ref": portal_ref,
                            "storage_uri": storage_uri,
                            "metadata": metadata,
                        },
                        sort_keys=True,
                    ),
                    "phase4-official-artifact-1",
                    normalized_kind,
                )

        refreshed = await self.latest_artifacts(thread_id)
        if not refreshed:
            raise KeyError(thread_id)
        return refreshed

    async def start_everification(
        self,
        *,
        thread_id: str,
        assessment_year: str,
        handoff: dict[str, Any],
    ) -> dict[str, Any]:
        record_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into everification_status (
                        id, thread_id, handoff_id, method, status,
                        target_url, handoff_json
                    )
                    values ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    on conflict (handoff_id) do update
                    set method = excluded.method,
                        status = excluded.status,
                        target_url = excluded.target_url,
                        handoff_json = excluded.handoff_json
                    """,
                    record_id,
                    thread_id,
                    handoff.get("handoff_id"),
                    handoff.get("method"),
                    handoff.get("status"),
                    handoff.get("target_url"),
                    json.dumps(handoff, sort_keys=True),
                )
                await connection.execute(
                    """
                    insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                    values ($1, $2, 'everify_started', $3::jsonb, $4, $5)
                    """,
                    uuid.uuid4(),
                    assessment_year,
                    json.dumps({"thread_id": thread_id, **handoff}, sort_keys=True),
                    "phase4-everify-1",
                    handoff.get("method") or "unknown",
                )
        return await self.latest_everification(thread_id)

    async def complete_everification(
        self,
        *,
        thread_id: str,
        assessment_year: str,
        handoff_id: str,
        portal_ref: Optional[str],
        verified_at: Optional[Any] = None,
    ) -> dict[str, Any]:
        verified_at_value = _normalize_timestamp(verified_at) or datetime.utcnow()
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """
                    update everification_status
                    set status = 'completed',
                        portal_ref = $3,
                        verified_at = $4
                    where thread_id = $1 and handoff_id = $2
                    returning id
                    """,
                    thread_id,
                    handoff_id,
                    portal_ref,
                    verified_at_value,
                )
                if not row:
                    raise KeyError(handoff_id)
                await connection.execute(
                    """
                    insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                    values ($1, $2, 'everified', $3::jsonb, $4, $5)
                    """,
                    uuid.uuid4(),
                    assessment_year,
                    json.dumps({
                        "thread_id": thread_id,
                        "handoff_id": handoff_id,
                        "portal_ref": portal_ref,
                        "verified_at": verified_at_value.isoformat(),
                    }, sort_keys=True),
                    "phase4-everify-1",
                    "manual",
                )
        latest = await self.latest_everification(thread_id)
        if not latest:
            raise KeyError(handoff_id)
        return latest

    async def record_revision_branch(
        self,
        *,
        base_thread_id: str,
        revision_thread_id: str,
        revision_number: int,
        reason: str,
        prior_return: dict[str, Any],
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into revision_threads (
                    id, base_thread_id, revision_thread_id, revision_number, reason, prior_return_json
                )
                values ($1, $2, $3, $4, $5, $6::jsonb)
                on conflict (revision_thread_id) do nothing
                """,
                uuid.uuid4(),
                base_thread_id,
                revision_thread_id,
                revision_number,
                reason,
                json.dumps(prior_return, sort_keys=True),
            )

    async def latest_submission_summary(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, draft_return_id, summary_json::text as summary_json, summary_md,
                       total_income, total_deductions, taxable_income, tax_payable,
                       refund_due, mismatches::text as mismatches, generated_at
                from submission_summaries
                where thread_id = $1
                order by generated_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_summary(row) if row else None

    async def latest_artifacts(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, ack_no, itr_v_storage_uri, json_export_uri,
                       evidence_bundle_uri, summary_storage_uri, filed_at,
                       artifact_manifest::text as artifact_manifest
                from filed_return_artifacts
                where thread_id = $1
                order by filed_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_artifacts(row) if row else None

    async def latest_everification(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, handoff_id, method, status, target_url, portal_ref,
                       handoff_json::text as handoff_json, created_at, verified_at
                from everification_status
                where thread_id = $1
                order by created_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_everification(row) if row else None

    async def latest_revision(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, base_thread_id, revision_thread_id, revision_number,
                       reason, prior_return_json::text as prior_return_json, created_at
                from revision_threads
                where base_thread_id = $1 or revision_thread_id = $1
                order by created_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_revision(row) if row else None

    async def record_year_over_year_comparison(
        self,
        *,
        thread_id: str,
        user_id: str,
        current_assessment_year: Optional[str],
        prior_thread_id: Optional[str],
        prior_assessment_year: Optional[str],
        comparison: dict[str, Any],
    ) -> dict[str, Any]:
        record_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into year_over_year_comparisons (
                    id, thread_id, user_id, current_assessment_year,
                    prior_thread_id, prior_assessment_year, comparison_json
                )
                values ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                record_id,
                thread_id,
                user_id,
                current_assessment_year,
                prior_thread_id,
                prior_assessment_year,
                json.dumps(comparison, sort_keys=True),
            )
        latest = await self.latest_year_over_year(thread_id)
        if not latest:
            raise KeyError(thread_id)
        return latest

    async def latest_year_over_year(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, user_id, current_assessment_year,
                       prior_thread_id, prior_assessment_year,
                       comparison_json::text as comparison_json, created_at
                from year_over_year_comparisons
                where thread_id = $1
                order by created_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_year_over_year(row) if row else None

    async def upsert_next_ay_checklist(
        self,
        *,
        thread_id: str,
        user_id: str,
        current_assessment_year: Optional[str],
        target_assessment_year: str,
        checklist: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        record_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into next_ay_checklists (
                    id, thread_id, user_id, current_assessment_year, target_assessment_year,
                    checklist_json, summary_json
                )
                values ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                on conflict (thread_id) do update
                set user_id = excluded.user_id,
                    current_assessment_year = excluded.current_assessment_year,
                    target_assessment_year = excluded.target_assessment_year,
                    checklist_json = excluded.checklist_json,
                    summary_json = excluded.summary_json,
                    updated_at = now()
                """,
                record_id,
                thread_id,
                user_id,
                current_assessment_year,
                target_assessment_year,
                json.dumps(checklist, sort_keys=True),
                json.dumps(summary, sort_keys=True),
            )
        latest = await self.latest_next_ay_checklist(thread_id)
        if not latest:
            raise KeyError(thread_id)
        return latest

    async def latest_next_ay_checklist(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, user_id, current_assessment_year, target_assessment_year,
                       checklist_json::text as checklist_json, summary_json::text as summary_json,
                       created_at, updated_at
                from next_ay_checklists
                where thread_id = $1
                limit 1
                """,
                thread_id,
            )
        return self._serialize_next_ay_checklist(row) if row else None

    async def record_notice_preparation(
        self,
        *,
        thread_id: str,
        user_id: str,
        notice_type: str,
        assessment_year: Optional[str],
        notice_text: str,
        extracted: dict[str, Any],
        explanation_md: str,
        suggested_response: dict[str, Any],
    ) -> dict[str, Any]:
        record_id = uuid.uuid4()
        storage_uri = f"notices/{thread_id}/{record_id}.txt"
        document_storage.write(storage_uri, notice_text.encode("utf-8"))
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into notice_response_preparations (
                    id, thread_id, user_id, notice_type, assessment_year,
                    source_storage_uri, extracted_json, explanation_md, suggested_response_json
                )
                values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9::jsonb)
                """,
                record_id,
                thread_id,
                user_id,
                notice_type,
                assessment_year,
                storage_uri,
                json.dumps(extracted, sort_keys=True),
                explanation_md,
                json.dumps(suggested_response, sort_keys=True),
            )
        latest = await self.latest_notice_preparation(thread_id)
        if not latest:
            raise KeyError(thread_id)
        return latest

    async def latest_notice_preparation(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, user_id, notice_type, assessment_year,
                       source_storage_uri, extracted_json::text as extracted_json,
                       explanation_md, suggested_response_json::text as suggested_response_json,
                       created_at, updated_at
                from notice_response_preparations
                where thread_id = $1
                order by created_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_notice_preparation(row) if row else None

    async def list_notice_preparations(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, thread_id, user_id, notice_type, assessment_year,
                       source_storage_uri, extracted_json::text as extracted_json,
                       explanation_md, suggested_response_json::text as suggested_response_json,
                       created_at, updated_at
                from notice_response_preparations
                where thread_id = $1
                order by created_at desc
                """,
                thread_id,
            )
        return [self._serialize_notice_preparation(row) for row in rows]

    async def record_refund_status(
        self,
        *,
        thread_id: str,
        user_id: str,
        assessment_year: Optional[str],
        status: str,
        refund_amount: Optional[float],
        portal_ref: Optional[str],
        issued_at: Optional[Any],
        processed_at: Optional[Any],
        refund_mode: Optional[str],
        bank_masked: Optional[str],
        source: str,
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        record_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into refund_status_snapshots (
                    id, thread_id, user_id, assessment_year, status, refund_amount,
                    portal_ref, issued_at, processed_at, refund_mode, bank_masked,
                    source, observation_json
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
                """,
                record_id,
                thread_id,
                user_id,
                assessment_year,
                status,
                refund_amount,
                portal_ref,
                _normalize_timestamp(issued_at),
                _normalize_timestamp(processed_at),
                refund_mode,
                bank_masked,
                source,
                json.dumps(observation, sort_keys=True),
            )
        latest = await self.latest_refund_status(thread_id)
        if not latest:
            raise KeyError(thread_id)
        return latest

    async def latest_refund_status(self, thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, user_id, assessment_year, status, refund_amount,
                       portal_ref, issued_at, processed_at, refund_mode, bank_masked,
                       source, observation_json::text as observation_json, observed_at
                from refund_status_snapshots
                where thread_id = $1
                order by observed_at desc
                limit 1
                """,
                thread_id,
            )
        return self._serialize_refund_status(row) if row else None

    async def list_consents(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, user_id, purpose, approval_key, scope::text as scope,
                       granted_at, revoked_at, response_hash
                from consents
                where thread_id = $1
                order by granted_at desc
                """,
                thread_id,
            )
        return [self._serialize_consent(row) for row in rows]

    def read_artifact(self, storage_uri: str) -> tuple[bytes, str]:
        return document_storage.read(storage_uri), _content_type_for_uri(storage_uri)

    def _serialize_summary(self, row: Record) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "draft_return_id": str(row["draft_return_id"]),
            "summary": json.loads(row["summary_json"] or "{}"),
            "summary_md": row["summary_md"],
            "total_income": _decimal_to_float(row["total_income"]),
            "total_deductions": _decimal_to_float(row["total_deductions"]),
            "taxable_income": _decimal_to_float(row["taxable_income"]),
            "tax_payable": _decimal_to_float(row["tax_payable"]),
            "refund_due": _decimal_to_float(row["refund_due"]),
            "mismatches": json.loads(row["mismatches"] or "[]"),
            "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
        }

    def _serialize_artifacts(self, row: Record) -> dict[str, Any]:
        return {
            "artifact_id": str(row["id"]),
            "ack_no": row["ack_no"],
            "itr_v_storage_uri": row["itr_v_storage_uri"],
            "json_export_uri": row["json_export_uri"],
            "evidence_bundle_uri": row["evidence_bundle_uri"],
            "summary_storage_uri": row["summary_storage_uri"],
            "filed_at": row["filed_at"].isoformat() if row["filed_at"] else None,
            "artifact_manifest": json.loads(row["artifact_manifest"] or "{}"),
        }

    def _serialize_everification(self, row: Record) -> dict[str, Any]:
        return {
            "record_id": str(row["id"]),
            "handoff_id": row["handoff_id"],
            "method": row["method"],
            "status": row["status"],
            "target_url": row["target_url"],
            "portal_ref": row["portal_ref"],
            "handoff": json.loads(row["handoff_json"] or "{}"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "verified_at": row["verified_at"].isoformat() if row["verified_at"] else None,
        }

    def _serialize_revision(self, row: Record) -> dict[str, Any]:
        return {
            "record_id": str(row["id"]),
            "base_thread_id": row["base_thread_id"],
            "revision_thread_id": row["revision_thread_id"],
            "revision_number": row["revision_number"],
            "reason": row["reason"],
            "prior_return": json.loads(row["prior_return_json"] or "{}"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    def _serialize_consent(self, row: Record) -> dict[str, Any]:
        return {
            "consent_id": str(row["id"]),
            "user_id": row["user_id"],
            "purpose": row["purpose"],
            "approval_key": row["approval_key"],
            "scope": json.loads(row["scope"] or "{}"),
            "granted_at": row["granted_at"].isoformat() if row["granted_at"] else None,
            "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
            "response_hash": row["response_hash"],
        }

    def _serialize_year_over_year(self, row: Record) -> dict[str, Any]:
        return {
            "record_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "user_id": row["user_id"],
            "current_assessment_year": row["current_assessment_year"],
            "prior_thread_id": row["prior_thread_id"],
            "prior_assessment_year": row["prior_assessment_year"],
            "comparison": json.loads(row["comparison_json"] or "{}"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    def _serialize_next_ay_checklist(self, row: Record) -> dict[str, Any]:
        return {
            "record_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "user_id": row["user_id"],
            "current_assessment_year": row["current_assessment_year"],
            "target_assessment_year": row["target_assessment_year"],
            "items": json.loads(row["checklist_json"] or "[]"),
            "summary": json.loads(row["summary_json"] or "{}"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    def _serialize_notice_preparation(self, row: Record) -> dict[str, Any]:
        return {
            "record_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "user_id": row["user_id"],
            "notice_type": row["notice_type"],
            "assessment_year": row["assessment_year"],
            "source_storage_uri": row["source_storage_uri"],
            "extracted": json.loads(row["extracted_json"] or "{}"),
            "explanation_md": row["explanation_md"],
            "suggested_response": json.loads(row["suggested_response_json"] or "{}"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    def _serialize_refund_status(self, row: Record) -> dict[str, Any]:
        return {
            "record_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "user_id": row["user_id"],
            "assessment_year": row["assessment_year"],
            "status": row["status"],
            "refund_amount": _decimal_to_float(row["refund_amount"]),
            "portal_ref": row["portal_ref"],
            "issued_at": row["issued_at"].isoformat() if row["issued_at"] else None,
            "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
            "refund_mode": row["refund_mode"],
            "bank_masked": row["bank_masked"],
            "source": row["source"],
            "observation": json.loads(row["observation_json"] or "{}"),
            "observed_at": row["observed_at"].isoformat() if row["observed_at"] else None,
        }

    # ------------------------------------------------------------------
    # ITR-U (Updated Return) persistence
    # ------------------------------------------------------------------

    async def record_itr_u_thread(
        self,
        *,
        base_thread_id: str,
        reason_code: str,
        reason_detail: str,
        base_ack_no: Optional[str],
        eligibility: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert a new itr_u_threads row in status 'awaiting_escalation'."""
        record_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into itr_u_threads (
                        id, base_thread_id, status, reason_code, reason_detail,
                        base_ack_no, eligibility_json
                    )
                    values ($1, $2, 'awaiting_escalation', $3, $4, $5, $6::jsonb)
                    """,
                    record_id,
                    base_thread_id,
                    reason_code,
                    reason_detail,
                    base_ack_no,
                    json.dumps(eligibility, sort_keys=True),
                )
                await connection.execute(
                    """
                    insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                    values ($1, $2, 'itr_u_prepared', $3::jsonb, $4, $5)
                    """,
                    uuid.uuid4(),
                    str(eligibility.get("assessment_year") or "unknown"),
                    json.dumps(
                        {
                            "base_thread_id": base_thread_id,
                            "reason_code": reason_code,
                            "base_ack_no": base_ack_no,
                        },
                        sort_keys=True,
                    ),
                    "phase4-itr-u-1",
                    "itr_u",
                )
        row = await self._fetch_itr_u_by_id(record_id)
        if not row:
            raise KeyError(base_thread_id)
        return self._serialize_itr_u(row)

    async def confirm_itr_u_escalation(
        self,
        *,
        base_thread_id: str,
        itr_u_thread_id: str,
        confirmed_by: str,
    ) -> dict[str, Any]:
        """Mark the ITR-U escalation confirmed and record the new thread ID."""
        now = datetime.utcnow()
        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """
                    update itr_u_threads
                    set status = 'escalation_confirmed',
                        itr_u_thread_id = $2,
                        escalation_confirmed_at = $3,
                        escalation_confirmed_by = $4,
                        updated_at = $3
                    where base_thread_id = $1
                      and status = 'awaiting_escalation'
                    returning id
                    """,
                    base_thread_id,
                    now,
                    confirmed_by,
                )
                if not row:
                    raise KeyError(base_thread_id)
                assessment_year = await connection.fetchval(
                    "select eligibility_json->>'assessment_year' from itr_u_threads where id = $1",
                    row["id"],
                )
                await connection.execute(
                    """
                    insert into filing_audit_trail (id, ay_id, event, payload, rule_version, adapter_version)
                    values ($1, $2, 'itr_u_escalation_confirmed', $3::jsonb, $4, $5)
                    """,
                    uuid.uuid4(),
                    str(assessment_year or "unknown"),
                    json.dumps(
                        {
                            "base_thread_id": base_thread_id,
                            "itr_u_thread_id": itr_u_thread_id,
                            "confirmed_by": confirmed_by,
                            "confirmed_at": now.isoformat(),
                        },
                        sort_keys=True,
                    ),
                    "phase4-itr-u-1",
                    "itr_u",
                )
        latest = await self.latest_itr_u(base_thread_id)
        if not latest:
            raise KeyError(base_thread_id)
        return latest

    async def latest_itr_u(self, base_thread_id: str) -> Optional[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, base_thread_id, itr_u_thread_id, status,
                       reason_code, reason_detail, base_ack_no,
                       eligibility_json::text as eligibility_json,
                       escalation_confirmed_at, escalation_confirmed_by,
                       created_at, updated_at
                from itr_u_threads
                where base_thread_id = $1
                order by created_at desc
                limit 1
                """,
                base_thread_id,
            )
        return self._serialize_itr_u(row) if row else None

    async def _fetch_itr_u_by_id(self, record_id: uuid.UUID) -> Optional[Record]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            return await connection.fetchrow(
                """
                select id, base_thread_id, itr_u_thread_id, status,
                       reason_code, reason_detail, base_ack_no,
                       eligibility_json::text as eligibility_json,
                       escalation_confirmed_at, escalation_confirmed_by,
                       created_at, updated_at
                from itr_u_threads
                where id = $1
                """,
                record_id,
            )

    def _serialize_itr_u(self, row: Record) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "base_thread_id": row["base_thread_id"],
            "itr_u_thread_id": row["itr_u_thread_id"],
            "status": row["status"],
            "reason_code": row["reason_code"],
            "reason_detail": row["reason_detail"],
            "base_ack_no": row["base_ack_no"],
            "eligibility": json.loads(row["eligibility_json"] or "{}"),
            "escalation_confirmed_at": (
                row["escalation_confirmed_at"].isoformat()
                if row["escalation_confirmed_at"]
                else None
            ),
            "escalation_confirmed_by": row["escalation_confirmed_by"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    def _render_itrv_placeholder(
        self,
        *,
        thread_id: str,
        assessment_year: str,
        itr_type: str,
        submission_summary: dict[str, Any],
        ack_no: Optional[str],
        portal_ref: Optional[str],
    ) -> str:
        return (
            "ITR-V placeholder archive\n"
            f"Thread ID: {thread_id}\n"
            f"Assessment Year: {assessment_year}\n"
            f"ITR Type: {itr_type}\n"
            f"Ack No: {ack_no or 'not_provided'}\n"
            f"Portal Ref: {portal_ref or 'not_provided'}\n"
            f"Refund Due: {submission_summary.get('refund_due', 0)}\n"
            f"Tax Payable: {submission_summary.get('tax_payable', 0)}\n\n"
            "The official ITR-V download remains portal-controlled.\n"
            "This archive preserves the filing context until the official artifact is attached.\n"
        )


filing_runtime = FilingRuntimeService()