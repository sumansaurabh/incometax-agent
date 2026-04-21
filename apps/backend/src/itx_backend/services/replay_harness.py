from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import hashlib


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
    def __init__(self) -> None:
        self._snapshots: dict[str, ReplaySnapshot] = {}
        self._runs: list[ReplayRun] = []

    def capture_snapshot(
        self,
        thread_id: str,
        page_type: str,
        dom_html: str,
        url: str,
        metadata: dict[str, Any] | None = None,
    ) -> ReplaySnapshot:
        raw = f"{thread_id}:{page_type}:{url}:{datetime.now(timezone.utc).isoformat()}"
        snapshot_id = hashlib.sha256(raw.encode()).hexdigest()[:20]
        snapshot = ReplaySnapshot(
            snapshot_id=snapshot_id,
            thread_id=thread_id,
            page_type=page_type,
            dom_html=dom_html,
            url=url,
            captured_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self._snapshots[snapshot_id] = snapshot
        return snapshot

    def replay(
        self,
        snapshot_id: str,
        expected_selectors: list[str],
    ) -> ReplayRun:
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            raise KeyError("snapshot_not_found")

        mismatches: list[dict[str, Any]] = []
        for selector in expected_selectors:
            if selector not in snapshot.dom_html:
                mismatches.append(
                    {
                        "selector": selector,
                        "reason": "selector_not_present_in_snapshot",
                    }
                )

        run = ReplayRun(
            run_id=hashlib.sha256(
                f"{snapshot_id}:{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:20],
            snapshot_id=snapshot_id,
            executed_at=datetime.now(timezone.utc).isoformat(),
            success=len(mismatches) == 0,
            mismatches=mismatches,
        )
        self._runs.append(run)
        return run

    def list_snapshots(self, thread_id: str | None = None) -> list[dict[str, Any]]:
        items = self._snapshots.values()
        if thread_id:
            items = [s for s in items if s.thread_id == thread_id]
        return [asdict(s) for s in items]

    def list_runs(self) -> list[dict[str, Any]]:
        return [asdict(r) for r in self._runs]

    def purge_thread(self, thread_id: str) -> None:
        snapshot_ids = {snapshot_id for snapshot_id, snapshot in self._snapshots.items() if snapshot.thread_id == thread_id}
        for snapshot_id in snapshot_ids:
            self._snapshots.pop(snapshot_id, None)
        self._runs = [run for run in self._runs if run.snapshot_id not in snapshot_ids]


replay_harness = ReplayHarness()
