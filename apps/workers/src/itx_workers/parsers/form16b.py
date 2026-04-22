from __future__ import annotations

from itx_workers.parsers.common import extract_assessment_year, extract_labeled_amount, extract_labeled_text, extract_pan


def parse(raw_text: str) -> dict:
    facts = {
        "pan": extract_pan(raw_text),
        "assessment_year": extract_assessment_year(raw_text),
        "name": extract_labeled_text(raw_text, ["Name of Seller", "Transferor", "Deductee"]),
        "tax_paid": {
            "tds_salary": 0.0,
            "tds_other": extract_labeled_amount(raw_text, ["Total tax deducted", "Tax deducted", "TDS"]) or 0.0,
        },
        "house_property": {
            "sale_consideration": extract_labeled_amount(raw_text, ["Total value of consideration", "Amount paid", "Property value"]) or 0.0,
        },
    }
    return {
        "parser": "form16b",
        "document_type": "form16b",
        "facts": facts,
        "warnings": [],
        "confidence": 0.78,
    }
