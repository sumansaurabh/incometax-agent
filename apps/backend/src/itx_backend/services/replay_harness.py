from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from typing import Any, Optional
import hashlib
import re

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
    def _selector_present(self, dom_html: str, selector: str) -> bool:
        selector = selector.strip()
        if not selector:
            return False

        if "," in selector:
            return any(self._selector_present(dom_html, part) for part in selector.split(","))

        id_match = re.fullmatch(r"#([A-Za-z_][\w\-:.]*)", selector)
        if id_match:
            return re.search(rf"id=['\"]{re.escape(id_match.group(1))}['\"]", dom_html, re.IGNORECASE) is not None

        attr_match = re.fullmatch(
            r"(?:[A-Za-z][\w-]*)?\[(?P<attr>[A-Za-z_:][\w:.-]*)=['\"]?(?P<value>[^'\"]+)['\"]?(?:\s+[iI])?\]",
            selector,
        )
        if attr_match:
            attr = re.escape(attr_match.group("attr"))
            value = re.escape(attr_match.group("value"))
            return re.search(rf"{attr}=['\"]{value}['\"]", dom_html, re.IGNORECASE) is not None

        tag_attr_match = re.fullmatch(
            r"(?P<tag>[A-Za-z][\w-]*)\[(?P<attr>[A-Za-z_:][\w:.-]*)=['\"]?(?P<value>[^'\"]+)['\"]?(?:\s+[iI])?\]",
            selector,
        )
        if tag_attr_match:
            tag = re.escape(tag_attr_match.group("tag"))
            attr = re.escape(tag_attr_match.group("attr"))
            value = re.escape(tag_attr_match.group("value"))
            return re.search(rf"<{tag}[^>]*{attr}=['\"]{value}['\"]", dom_html, re.IGNORECASE) is not None

        return selector in dom_html

    def _selectors_from_metadata(self, metadata: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        raw_selectors = metadata.get("expected_selectors") or metadata.get("selectors") or metadata.get("resolved_selectors")
        if isinstance(raw_selectors, list):
            candidates.extend(str(item) for item in raw_selectors if str(item).strip())

        fields = metadata.get("fields")
        if isinstance(fields, list):
            for field in fields:
                if isinstance(field, dict) and field.get("selectorHint"):
                    candidates.append(str(field["selectorHint"]))

        portal_state = metadata.get("portal_state")
        if isinstance(portal_state, dict):
            portal_fields = portal_state.get("fields")
            if isinstance(portal_fields, dict):
                for key, value in portal_fields.items():
                    if isinstance(key, str) and any(token in key for token in ("#", "[", ".")):
                        candidates.append(key)
                    if isinstance(value, dict):
                        selector = value.get("selector") or value.get("selectorHint")
                        if selector:
                            candidates.append(str(selector))

        return list(dict.fromkeys(selector for selector in candidates if selector))

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
            if not self._selector_present(snapshot.dom_html, selector):
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

    async def dashboard(self) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            totals = await connection.fetchrow(
                """
                select
                    (select count(*) from replay_snapshots) as snapshots,
                    (select count(*) from replay_runs) as runs,
                    (select count(*) from replay_runs where success = true) as successful_runs,
                    (select count(*) from replay_runs where success = false) as failed_runs
                """
            )
            page_rows = await connection.fetch(
                """
                select s.page_type,
                       count(r.run_id) as runs,
                       count(*) filter (where r.success = true) as successful_runs,
                       count(*) filter (where r.success = false) as failed_runs
                from replay_snapshots s
                left join replay_runs r on r.snapshot_id = s.snapshot_id
                group by s.page_type
                order by s.page_type asc
                """
            )
            mismatch_rows = await connection.fetch(
                """
                select mismatches::text as mismatches
                from replay_runs
                where success = false
                order by executed_at desc
                limit 50
                """
            )

        failed_runs = int(totals["failed_runs"] if totals else 0)
        total_runs = int(totals["runs"] if totals else 0)
        selector_failures: dict[str, int] = {}
        for row in mismatch_rows:
            for mismatch in json.loads(row["mismatches"] or "[]"):
                selector = str(mismatch.get("selector") or mismatch.get("reason") or "unknown")
                selector_failures[selector] = selector_failures.get(selector, 0) + 1

        return {
            "totals": {
                "snapshots": int(totals["snapshots"] if totals else 0),
                "runs": total_runs,
                "successful_runs": int(totals["successful_runs"] if totals else 0),
                "failed_runs": failed_runs,
                "success_rate": round(((total_runs - failed_runs) / total_runs) if total_runs else 1.0, 4),
            },
            "by_page": {
                row["page_type"]: {
                    "runs": int(row["runs"] or 0),
                    "successful_runs": int(row["successful_runs"] or 0),
                    "failed_runs": int(row["failed_runs"] or 0),
                }
                for row in page_rows
            },
            "top_selector_failures": [
                {"selector": selector, "count": count}
                for selector, count in sorted(selector_failures.items(), key=lambda item: (-item[1], item[0]))[:10]
            ],
        }

    async def run_regression_pipeline(
        self,
        *,
        thread_id: Optional[str] = None,
        page_type: Optional[str] = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            clauses = []
            params: list[Any] = []
            if thread_id is not None:
                clauses.append(f"thread_id = ${len(params) + 1}")
                params.append(thread_id)
            if page_type is not None:
                clauses.append(f"page_type = ${len(params) + 1}")
                params.append(page_type)
            where_clause = f"where {' and '.join(clauses)}" if clauses else ""
            params.append(limit)
            rows = await connection.fetch(
                f"""
                select snapshot_id, thread_id, page_type, metadata::text as metadata
                from replay_snapshots
                {where_clause}
                order by captured_at desc
                limit ${len(params)}
                """,
                *params,
            )

        totals = {
            "snapshots_considered": len(rows),
            "snapshots_with_selectors": 0,
            "runs_created": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "skipped_snapshots": 0,
        }
        by_page: dict[str, dict[str, int]] = {}
        items: list[dict[str, Any]] = []

        for row in rows:
            metadata = json.loads(row["metadata"] or "{}")
            selectors = self._selectors_from_metadata(metadata)
            page_key = str(row["page_type"] or "unknown")
            page_totals = by_page.setdefault(
                page_key,
                {"snapshots": 0, "runs": 0, "successes": 0, "failures": 0, "skipped": 0},
            )
            page_totals["snapshots"] += 1

            if not selectors:
                totals["skipped_snapshots"] += 1
                page_totals["skipped"] += 1
                items.append(
                    {
                        "snapshot_id": row["snapshot_id"],
                        "thread_id": row["thread_id"],
                        "page_type": page_key,
                        "status": "skipped",
                        "reason": "no_expected_selectors_in_metadata",
                    }
                )
                continue

            totals["snapshots_with_selectors"] += 1
            run = await self.replay(str(row["snapshot_id"]), selectors)
            totals["runs_created"] += 1
            page_totals["runs"] += 1
            if run.success:
                totals["successful_runs"] += 1
                page_totals["successes"] += 1
            else:
                totals["failed_runs"] += 1
                page_totals["failures"] += 1

            items.append(
                {
                    "snapshot_id": row["snapshot_id"],
                    "thread_id": row["thread_id"],
                    "page_type": page_key,
                    "status": "passed" if run.success else "failed",
                    "expected_selectors": selectors,
                    "mismatches": run.mismatches,
                    "run_id": run.run_id,
                }
            )

        success_rate = (
            round(totals["successful_runs"] / totals["runs_created"], 4)
            if totals["runs_created"]
            else 1.0
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": {"thread_id": thread_id, "page_type": page_type, "limit": limit},
            "totals": {**totals, "success_rate": success_rate},
            "by_page": by_page,
            "items": items,
        }

    async def purge_thread(self, thread_id: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("delete from replay_snapshots where thread_id = $1", thread_id)


replay_harness = ReplayHarness()
