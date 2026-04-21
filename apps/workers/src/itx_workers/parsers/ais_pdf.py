from __future__ import annotations

from itx_workers.parsers.common import extract_assessment_year, extract_labeled_amount, extract_pan


def parse(raw_text: str) -> dict:
    facts = {
        "pan": extract_pan(raw_text),
        "assessment_year": extract_assessment_year(raw_text),
        "salary": {"gross": extract_labeled_amount(raw_text, ["Gross Salary", "Salary as per AIS"]) or 0.0},
        "tax_paid": {
            "tds_salary": extract_labeled_amount(raw_text, ["TDS on Salary", "Salary TDS"]) or 0.0,
            "tds_other": extract_labeled_amount(raw_text, ["TDS on Other", "Other TDS"]) or 0.0,
        },
        "other_sources": {"total": extract_labeled_amount(raw_text, ["Interest Income", "Dividend Income"]) or 0.0},
    }
    return {
        "parser": "ais_pdf",
        "document_type": "ais_pdf",
        "facts": facts,
        "warnings": [],
        "confidence": 0.74,
    }
