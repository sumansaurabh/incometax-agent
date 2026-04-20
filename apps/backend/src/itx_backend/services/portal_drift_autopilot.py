from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class PortalDriftAutopilot:
    def run(self, drift_items: list[dict[str, Any]]) -> dict[str, Any]:
        grouped: dict[tuple[str, str], int] = defaultdict(int)
        for item in drift_items:
            grouped[(item.get("page_type", "unknown"), item.get("selector", ""))] += 1

        recommendations = []
        for (page_type, selector), count in grouped.items():
            if count < 3:
                continue
            recommendations.append(
                {
                    "page_type": page_type,
                    "selector": selector,
                    "failure_count": count,
                    "actions": [
                        "refresh_selector_candidates",
                        "add_fallback_chain",
                        "add_snapshot_test",
                    ],
                }
            )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "recommendation_count": len(recommendations),
            "recommendations": recommendations,
            "pr_template": {
                "title": "chore(portal-adapters): nightly drift regeneration",
                "body": "Auto-generated from drift telemetry.",
            },
        }


portal_drift_autopilot = PortalDriftAutopilot()
