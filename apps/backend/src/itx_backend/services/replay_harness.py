from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from typing import Any, Optional
import hashlib

from itx_backend.db.session import get_pool


@dataclass
class ReplaySnapshot:
    snapshot_id: str
    thread_id: str
    page_type: str
    dom_html: str
    url: str
    captured_at: str
    metadata: dict[str, Any]


@dataclass
class ReplayRun:
    run_id: str
    snapshot_id: str
    executed_at: str
    success: bool
    mismatches: list[dict[str, Any]]


class ReplayHarness:
    async def capture_snapshot(
        self,
        thread_id: str,
        page_type: str,
        dom_html: str,
        url: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ReplaySnapshot:
        captured_at_dt = datetime.now(timezone.utc)
        raw = f"{thread_id}:{page_type}:{url}:{captured_at_dt.isoformat()}"
        snapshot_id = hashlib.sha256(raw.encode()).hexdigest()[:20]
        snapshot = ReplaySnapshot(
            snapshot_id=snapshot_id,
            thread_id=thread_id,
            page_type=page_type,
            dom_html=dom_html,
            url=url,
            captured_at=captured_at_dt.isoformat(),
            metadata=metadata or {},
        )
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into replay_snapshots (
                    snapshot_id, thread_id, page_type, dom_html, url, metadata, captured_at
                )
                values ($1, $2, $3, $4, $5, $6::jsonb, $7)
                """,
                snapshot.snapshot_id,
                snapshot.thread_id,
                snapshot.page_type,
                snapshot.dom_html,
                snapshot.url,
                json.dumps(snapshot.metadata, sort_keys=True),
                captured_at_dt,
            )
        return snapshot

    async def replay(
        self,
        snapshot_id: str,
        expected_selectors: list[str],
    ) -> ReplayRun:
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select snapshot_id, thread_id, page_type, dom_html, url, metadata::text as metadata, captured_at
                from replay_snapshots
                where snapshot_id = $1
                """,
                snapshot_id,
            )
        if not row:
            raise KeyError("snapshot_not_found")

        snapshot = ReplaySnapshot(
            snapshot_id=row["snapshot_id"],
            thread_id=row["thread_id"],
            page_type=row["page_type"],
            dom_html=row["dom_html"],
            url=row["url"],
            captured_at=row["captured_at"].isoformat() if row["captured_at"] else datetime.now(timezone.utc).isoformat(),
            metadata=json.loads(row["metadata"] or "{}"),
        )

        mismatches: list[dict[str, Any]] = []
        for selector in expected_selectors:
            if selector not in snapshot.dom_html:
                mismatches.append(
                    {
                        "selector": selector,
                        "reason": "selector_not_present_in_snapshot",
                    }
                )

        executed_at_dt = datetime.now(timezone.utc)
        run = ReplayRun(
            run_id=hashlib.sha256(
                f"{snapshot_id}:{executed_at_dt.isoformat()}".encode()
            ).hexdigest()[:20],
            snapshot_id=snapshot_id,
            executed_at=executed_at_dt.isoformat(),
            success=len(mismatches) == 0,
            mismatches=mismatches,
        )
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into replay_runs (run_id, snapshot_id, thread_id, success, mismatches, executed_at)
                values ($1, $2, $3, $4, $5::jsonb, $6)
                """,
                run.run_id,
                run.snapshot_id,
                snapshot.thread_id,
                run.success,
                json.dumps(run.mismatches, sort_keys=True),
                executed_at_dt,
            )
        return run

    async def list_snapshots(self, thread_id: Optional[str] = None) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            if thread_id:
                rows = await connection.fetch(
                    """
                    select snapshot_id, thread_id, page_type, dom_html, url, metadata::text as metadata, captured_at
                    from replay_snapshots
                    where thread_id = $1
                    order by captured_at desc
                    """,
                    thread_id,
                )
            else:
                rows = await connection.fetch(
                    """
                    select snapshot_id, thread_id, page_type, dom_html, url, metadata::text as metadata, captured_at
                    from replay_snapshots
                    order by captured_at desc
                    """
                )
        return [
            asdict(
                ReplaySnapshot(
                    snapshot_id=row["snapshot_id"],
                    thread_id=row["thread_id"],
                    page_type=row["page_type"],
                    dom_html=row["dom_html"],
                    url=row["url"],
                    captured_at=row["captured_at"].isoformat() if row["captured_at"] else datetime.now(timezone.utc).isoformat(),
                    metadata=json.loads(row["metadata"] or "{}"),
                )
            )
            for row in rows
        ]

    async def list_runs(self, thread_id: Optional[str] = None) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            if thread_id:
                rows = await connection.fetch(
                    """
                    select run_id, snapshot_id, success, mismatches::text as mismatches, executed_at
                    from replay_runs
                    where thread_id = $1
                    order by executed_at desc
                    """,
                    thread_id,
                )
            else:
                rows = await connection.fetch(
                    """
                    select run_id, snapshot_id, success, mismatches::text as mismatches, executed_at
                    from replay_runs
                    order by executed_at desc
                    """
                )
        return [
            asdict(
                ReplayRun(
                    run_id=row["run_id"],
                    snapshot_id=row["snapshot_id"],
                    executed_at=row["executed_at"].isoformat() if row["executed_at"] else datetime.now(timezone.utc).isoformat(),
                    success=row["success"],
                    mismatches=json.loads(row["mismatches"] or "[]"),
                )
            )
            for row in rows
        ]

    async def purge_thread(self, thread_id: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("delete from replay_snapshots where thread_id = $1", thread_id)


replay_harness = ReplayHarness()
