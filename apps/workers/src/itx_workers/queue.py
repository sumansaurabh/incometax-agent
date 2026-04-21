from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import asyncpg


DATABASE_URL = os.getenv("ITX_DATABASE_URL", "postgresql://itx:itx@localhost:5432/itx")


@dataclass
class QueueJob:
    document_id: str
    doc_type: str
    thread_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str = "queued"
    attempts: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


async def enqueue(job: QueueJob) -> QueueJob:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        job_id = str(uuid.uuid4())
        await connection.execute(
            """
            insert into document_jobs (id, document_id, thread_id, doc_type, status, payload)
            values ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            uuid.UUID(job_id),
            uuid.UUID(job.document_id),
            job.thread_id,
            job.doc_type,
            "queued",
            json.dumps(job.payload, sort_keys=True),
        )
        job.job_id = job_id
        job.status = "queued"
        return job
    finally:
        await connection.close()


async def claim_next(document_id: Optional[str] = None) -> Optional[QueueJob]:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        if document_id:
            row = await connection.fetchrow(
                """
                update document_jobs
                set status = 'processing',
                    attempts = attempts + 1,
                    started_at = now()
                where id = (
                    select id
                    from document_jobs
                    where status = 'queued' and document_id = $1
                    order by created_at asc
                    for update skip locked
                    limit 1
                )
                returning id, document_id, thread_id, doc_type, status, attempts, payload::text as payload
                """,
                uuid.UUID(document_id),
            )
        else:
            row = await connection.fetchrow(
                """
                update document_jobs
                set status = 'processing',
                    attempts = attempts + 1,
                    started_at = now()
                where id = (
                    select id
                    from document_jobs
                    where status = 'queued'
                    order by created_at asc
                    for update skip locked
                    limit 1
                )
                returning id, document_id, thread_id, doc_type, status, attempts, payload::text as payload
                """
            )
        if not row:
            return None
        return QueueJob(
            job_id=str(row["id"]),
            document_id=str(row["document_id"]),
            thread_id=row["thread_id"],
            doc_type=row["doc_type"],
            status=row["status"],
            attempts=row["attempts"],
            payload=json.loads(row["payload"] or "{}"),
        )
    finally:
        await connection.close()


async def complete(job_id: str) -> None:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        await connection.execute(
            """
            update document_jobs
            set status = 'completed',
                completed_at = now(),
                last_error = null
            where id = $1
            """,
            uuid.UUID(job_id),
        )
    finally:
        await connection.close()


async def fail(job_id: str, error_text: str) -> None:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        await connection.execute(
            """
            update document_jobs
            set status = 'failed',
                completed_at = now(),
                last_error = $2
            where id = $1
            """,
            uuid.UUID(job_id),
            error_text[:2000],
        )
    finally:
        await connection.close()


async def drain(
    processor: Callable[[QueueJob], Awaitable[dict[str, Any]]],
    *,
    limit: int = 10,
    document_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    processed = 0
    while processed < limit:
        job = await claim_next(document_id=document_id)
        if job is None:
            break
        try:
            result = await processor(job)
        except Exception as exc:
            await fail(job.job_id or "", str(exc))
            raise
        await complete(job.job_id or "")
        results.append(result)
        processed += 1
        if document_id:
            break
    return results
