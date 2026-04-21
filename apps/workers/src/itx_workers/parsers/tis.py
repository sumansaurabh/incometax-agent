from __future__ import annotations

from itx_workers.parsers.common import extract_assessment_year, extract_labeled_amount, extract_pan


def parse(raw_text: str) -> dict:
    facts = {
        "pan": extract_pan(raw_text),
        "assessment_year": extract_assessment_year(raw_text),
        "salary": {"gross": extract_labeled_amount(raw_text, ["Salary", "Salary Income"]) or 0.0},
        "other_sources": {"total": extract_labeled_amount(raw_text, ["Income from Other Sources", "Interest Income"]) or 0.0},
        "capital_gains": {
            "stcg": extract_labeled_amount(raw_text, ["STCG", "Short Term Capital Gain"]) or 0.0,
            "ltcg": extract_labeled_amount(raw_text, ["LTCG", "Long Term Capital Gain"]) or 0.0,
        },
    }
    return {
        "parser": "tis",
        "document_type": "tis",
        "facts": facts,
        "warnings": [],
        "confidence": 0.78,
    }
