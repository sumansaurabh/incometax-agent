from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from itx_backend.config import settings
from itx_backend.db.session import get_pool
from itx_backend.services.analytics import analytics_service
from itx_backend.services.document_storage import document_storage
from itx_backend.services.replay_harness import replay_harness


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RetentionService:
    def __init__(self) -> None:
        self._last_sweep_at: Optional[datetime] = None

    async def revoke_consent_and_queue_purge(
        self,
        *,
        consent_id: str,
        thread_id: str,
        requested_by: str,
        reason: str,
        process_immediately: bool = True,
    ) -> dict[str, Any]:
        pool = await get_pool()
        job_id = uuid.uuid4()
        async with pool.acquire() as connection:
            async with connection.transaction():
                consent_row = await connection.fetchrow(
                    """
                    update consents
                    set revoked_at = coalesce(revoked_at, now())
                    where id = $1::uuid and thread_id = $2
                    returning id, thread_id, user_id, purpose, approval_key, scope::text as scope,
                              granted_at, revoked_at, response_hash
                    """,
                    consent_id,
                    thread_id,
                )
                if consent_row is None:
                    raise KeyError("consent_not_found")
                await connection.execute(
                    """
                    insert into purge_jobs (id, thread_id, reason, requested_by, status, due_at, details)
                    values ($1, $2, $3, $4, 'queued', now(), $5::jsonb)
                    """,
                    job_id,
                    thread_id,
                    reason,
                    requested_by,
                    json.dumps({"consent_id": consent_id, "purpose": consent_row["purpose"]}, sort_keys=True),
                )

        job = await self.get_purge_job(str(job_id))
        if process_immediately:
            processed = await self.process_due_purges(limit=1)
            if processed:
                job = processed[0]

        return {
            "consent": {
                "consent_id": str(consent_row["id"]),
                "thread_id": consent_row["thread_id"],
                "user_id": consent_row["user_id"],
                "purpose": consent_row["purpose"],
                "approval_key": consent_row["approval_key"],
                "scope": json.loads(consent_row["scope"] or "{}"),
                "granted_at": consent_row["granted_at"].isoformat() if consent_row["granted_at"] else None,
                "revoked_at": consent_row["revoked_at"].isoformat() if consent_row["revoked_at"] else None,
                "response_hash": consent_row["response_hash"],
            },
            "purge_job": job,
        }

    async def enqueue_due_retention_purges(self) -> int:
        threshold = _utcnow() - timedelta(days=settings.retention_purge_days)
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select distinct f.thread_id
                from filed_return_artifacts f
                where f.filed_at <= $1
                  and not exists (
                      select 1 from purge_jobs p
                      where p.thread_id = f.thread_id
                        and p.reason = 'retention_expiry'
                  )
                """,
                threshold,
            )
            for row in rows:
                await connection.execute(
                    """
                    insert into purge_jobs (id, thread_id, reason, requested_by, status, due_at, details)
                    values ($1, $2, 'retention_expiry', 'system', 'queued', now(), $3::jsonb)
                    """,
                    uuid.uuid4(),
                    row["thread_id"],
                    json.dumps({"retention_days": settings.retention_purge_days}, sort_keys=True),
                )
        return len(rows)

    async def maybe_run_due_purges(self) -> None:
        now = _utcnow()
        if self._last_sweep_at is not None and (now - self._last_sweep_at).total_seconds() < settings.retention_sweep_interval_seconds:
            return
        self._last_sweep_at = now
        await self.enqueue_due_retention_purges()
        await self.process_due_purges(limit=5)

    async def process_due_purges(self, *, limit: int = 10) -> list[dict[str, Any]]:
        pool = await get_pool()
        processed: list[dict[str, Any]] = []
        for _ in range(limit):
            async with pool.acquire() as connection:
                async with connection.transaction():
                    row = await connection.fetchrow(
                        """
                        select id, thread_id, reason, requested_by, requested_at, due_at, details::text as details
                        from purge_jobs
                        where status = 'queued' and due_at <= now()
                        order by due_at asc, requested_at asc
                        for update skip locked
                        limit 1
                        """
                    )
                    if row is None:
                        break
                    await connection.execute(
                        "update purge_jobs set status = 'running', started_at = now() where id = $1",
                        row["id"],
                    )

            details = await self._purge_thread_data(row["thread_id"])

            async with pool.acquire() as connection:
                await connection.execute(
                    """
                    update purge_jobs
                    set status = 'completed', completed_at = now(), details = details || $2::jsonb
                    where id = $1
                    """,
                    row["id"],
                    json.dumps(details, sort_keys=True),
                )
            processed.append(await self.get_purge_job(str(row["id"])))
        return processed

    async def list_purge_jobs(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, thread_id, reason, requested_by, status, requested_at, due_at,
                       started_at, completed_at, details::text as details
                from purge_jobs
                where thread_id = $1
                order by requested_at desc
                """,
                thread_id,
            )
        return [self._serialize_job(row) for row in rows]

    async def get_purge_job(self, job_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, reason, requested_by, status, requested_at, due_at,
                       started_at, completed_at, details::text as details
                from purge_jobs
                where id = $1::uuid
                """,
                job_id,
            )
        if row is None:
            raise KeyError("purge_job_not_found")
        return self._serialize_job(row)

    async def _purge_thread_data(self, thread_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            document_rows = await connection.fetch(
                """
                select dv.storage_uri
                from documents d
                join document_versions dv on dv.document_id = d.id
                where d.thread_id = $1
                """,
                thread_id,
            )
            artifact_rows = await connection.fetch(
                """
                select itr_v_storage_uri, json_export_uri, evidence_bundle_uri, summary_storage_uri
                from filed_return_artifacts
                where thread_id = $1
                """,
                thread_id,
            )

        deleted_paths = 0
        for row in document_rows:
            if row["storage_uri"] and document_storage.delete(row["storage_uri"]):
                deleted_paths += 1
        for row in artifact_rows:
            for key in ("itr_v_storage_uri", "json_export_uri", "evidence_bundle_uri", "summary_storage_uri"):
                if row[key] and document_storage.delete(row[key]):
                    deleted_paths += 1

        await analytics_service.purge_thread(thread_id)
        await replay_harness.purge_thread(thread_id)

        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("update consents set revoked_at = coalesce(revoked_at, now()) where thread_id = $1", thread_id)
                await connection.execute("delete from validation_errors where thread_id = $1", thread_id)
                await connection.execute("delete from field_fill_history where thread_id = $1", thread_id)
                await connection.execute("delete from approvals where thread_id = $1", thread_id)
                await connection.execute("delete from action_executions where thread_id = $1", thread_id)
                await connection.execute("delete from action_proposals where thread_id = $1", thread_id)
                await connection.execute("delete from submission_summaries where thread_id = $1", thread_id)
                await connection.execute("delete from draft_returns where thread_id = $1", thread_id)
                await connection.execute("delete from everification_status where thread_id = $1", thread_id)
                await connection.execute("delete from filed_return_artifacts where thread_id = $1", thread_id)
                await connection.execute("delete from revision_threads where base_thread_id = $1 or revision_thread_id = $1", thread_id)
                await connection.execute("delete from documents where thread_id = $1", thread_id)
                await connection.execute("delete from agent_checkpoints where thread_id = $1", thread_id)

        return {
            "thread_id": thread_id,
            "deleted_storage_paths": deleted_paths,
            "purged_at": _utcnow().isoformat(),
        }

    def _serialize_job(self, row: Any) -> dict[str, Any]:
        return {
            "job_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "reason": row["reason"],
            "requested_by": row["requested_by"],
            "status": row["status"],
            "requested_at": row["requested_at"].isoformat() if row["requested_at"] else None,
            "due_at": row["due_at"].isoformat() if row["due_at"] else None,
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "details": json.loads(row["details"] or "{}"),
        }


retention_service = RetentionService()