from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount


def parse(raw_text: str) -> dict:
    amount = extract_labeled_amount(raw_text, ["Invested Amount", "Contribution", "Premium Paid", "Deposit Amount"])
    facts = {
        "deductions": {"80c": amount or 0.0},
    }
    return {
        "parser": "elss_ppf",
        "document_type": "elss_ppf",
        "facts": facts,
        "warnings": [],
        "confidence": 0.8,
    }
