from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from itx_backend.services.replay_harness import replay_harness

router = APIRouter(prefix="/api/replay", tags=["replay"])


class CaptureSnapshotRequest(BaseModel):
    thread_id: str
    page_type: str
    dom_html: str
    url: str
    metadata: dict = {}


class ReplayRequest(BaseModel):
    snapshot_id: str
    expected_selectors: list[str]


@router.post("/capture")
def capture(payload: CaptureSnapshotRequest) -> dict:
    snapshot = replay_harness.capture_snapshot(
        thread_id=payload.thread_id,
        page_type=payload.page_type,
        dom_html=payload.dom_html,
        url=payload.url,
        metadata=payload.metadata,
    )
    return {
        "snapshot_id": snapshot.snapshot_id,
        "thread_id": snapshot.thread_id,
        "captured_at": snapshot.captured_at,
    }


@router.post("/run")
def replay(payload: ReplayRequest) -> dict:
    run = replay_harness.replay(payload.snapshot_id, payload.expected_selectors)
    return {
        "run_id": run.run_id,
        "success": run.success,
        "mismatches": run.mismatches,
        "executed_at": run.executed_at,
    }


@router.get("/snapshots")
def snapshots(thread_id: Optional[str] = None) -> dict:
    return {"items": replay_harness.list_snapshots(thread_id=thread_id)}


@router.get("/runs")
def runs() -> dict:
    return {"items": replay_harness.list_runs()}
