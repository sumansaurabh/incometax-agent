"""
Portal-drift autopilot job.

Nightly workflow:
1) Pull selector drift events from telemetry export
2) Group by page + selector
3) Emit adapter-regeneration recommendations
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class DriftRecommendation:
    page_type: str
    selector: str
    failure_count: int
    recommendation: str


class DriftAutopilot:
    def analyze(self, drift_events: list[dict[str, Any]]) -> list[DriftRecommendation]:
        grouped: dict[tuple[str, str], int] = defaultdict(int)
        for event in drift_events:
            key = (event.get("page_type", "unknown"), event.get("selector", ""))
            grouped[key] += 1

        recs: list[DriftRecommendation] = []
        for (page_type, selector), count in grouped.items():
            if count < 3:
                continue
            recs.append(
                DriftRecommendation(
                    page_type=page_type,
                    selector=selector,
                    failure_count=count,
                    recommendation=(
                        "Regenerate adapter selector candidates, add fallback strategy, "
                        "and include snapshot regression test."
                    ),
                )
            )
        return recs

    def build_pr_payload(self, recommendations: list[DriftRecommendation]) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "chore(portal-adapters): drift autopilot selector refresh",
            "body": "Nightly drift autopilot recommendations.",
            "changes": [
                {
                    "page_type": r.page_type,
                    "selector": r.selector,
                    "failures": r.failure_count,
                    "recommendation": r.recommendation,
                }
                for r in recommendations
            ],
        }



def run(payload: dict[str, Any]) -> dict[str, Any]:
    autopilot = DriftAutopilot()
    recs = autopilot.analyze(payload.get("drift_events", []))
    return {
        **payload,
        "stage": "drift_autopilot",
        "recommendation_count": len(recs),
        "recommendations": [
            {
                "page_type": r.page_type,
                "selector": r.selector,
                "failure_count": r.failure_count,
                "recommendation": r.recommendation,
            }
            for r in recs
        ],
        "pr_payload": autopilot.build_pr_payload(recs),
    }
