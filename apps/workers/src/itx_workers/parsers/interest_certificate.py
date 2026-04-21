from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount, extract_labeled_text, extract_pan, extract_ifsc


def parse(raw_text: str) -> dict:
    interest_total = extract_labeled_amount(raw_text, ["Interest Amount", "Total Interest", "Interest Paid", "Interest Credited"])
    tds_other = extract_labeled_amount(raw_text, ["TDS", "Tax Deducted"])
    facts = {
        "pan": extract_pan(raw_text),
        "other_sources": {"total": interest_total or 0.0},
        "tax_paid": {"tds_salary": 0.0, "tds_other": tds_other or 0.0},
        "bank": {
            "name": extract_labeled_text(raw_text, ["Bank Name", "Institution"]),
            "ifsc": extract_ifsc(raw_text),
        },
    }
    return {
        "parser": "interest_certificate",
        "document_type": "interest_certificate",
        "facts": facts,
        "warnings": [],
        "confidence": 0.86,
    }
