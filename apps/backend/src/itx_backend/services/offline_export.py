from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class OfflineUtilityExporter:
    """
    Produces portal-compatible JSON payload for offline utility fallback.
    """

    def export(self, tax_facts: dict[str, Any], assessment_year: str, itr_type: str) -> dict[str, Any]:
        # Shape intentionally deterministic and versioned.
        payload = {
            "schema_version": "itx-offline-1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "assessment_year": assessment_year,
            "itr_type": itr_type,
            "taxpayer": {
                "pan": tax_facts.get("pan"),
                "name": tax_facts.get("name"),
                "dob": tax_facts.get("dob"),
                "residential_status": tax_facts.get("residential_status"),
            },
            "income": {
                "salary": tax_facts.get("salary", {}),
                "house_property": tax_facts.get("house_property", {}),
                "capital_gains": tax_facts.get("capital_gains", {}),
                "other_sources": tax_facts.get("other_sources", {}),
            },
            "deductions": tax_facts.get("deductions", {}),
            "tax_paid": tax_facts.get("tax_paid", {}),
            "bank": tax_facts.get("bank", {}),
            "meta": {
                "regime": tax_facts.get("regime"),
                "source": "income-tax-agent",
            },
        }
        return payload


offline_exporter = OfflineUtilityExporter()
