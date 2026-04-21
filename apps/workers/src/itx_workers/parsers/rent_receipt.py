from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount, extract_labeled_text


def parse(raw_text: str) -> dict:
    hra = extract_labeled_amount(raw_text, ["HRA Exemption", "HRA Eligible", "Rent Paid"])
    facts = {
        "name": extract_labeled_text(raw_text, ["Tenant", "Name"]),
        "exemptions": {"hra": hra or 0.0},
    }
    return {
        "parser": "rent_receipt",
        "document_type": "rent_receipt",
        "facts": facts,
        "warnings": [],
        "confidence": 0.72,
    }
