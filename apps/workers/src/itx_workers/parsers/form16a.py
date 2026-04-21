from __future__ import annotations

from itx_workers.parsers.common import extract_assessment_year, extract_labeled_amount, extract_labeled_text, extract_pan


def parse(raw_text: str) -> dict:
    tds_other = extract_labeled_amount(raw_text, ["Tax deducted", "Total tax deducted", "TDS deducted"])
    interest = extract_labeled_amount(raw_text, ["Amount paid / credited", "Amount Paid", "Interest paid"])
    facts = {
        "pan": extract_pan(raw_text),
        "name": extract_labeled_text(raw_text, ["Deductee", "Name of Deductee"]),
        "assessment_year": extract_assessment_year(raw_text),
        "tax_paid": {"tds_salary": 0.0, "tds_other": tds_other or 0.0},
        "other_sources": {"total": interest or 0.0},
    }
    return {
        "parser": "form16a",
        "document_type": "form16a",
        "facts": facts,
        "warnings": [],
        "confidence": 0.87,
    }
