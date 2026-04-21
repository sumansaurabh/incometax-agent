from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount, extract_labeled_text


def parse(raw_text: str) -> dict:
    gross = extract_labeled_amount(raw_text, ["Gross Salary", "Gross Earnings", "Gross Pay"])
    facts = {
        "name": extract_labeled_text(raw_text, ["Employee Name", "Name"]),
        "employer_name": extract_labeled_text(raw_text, ["Employer", "Company", "Organization"]),
        "salary": {"gross": gross or 0.0},
    }
    return {
        "parser": "salary_slip",
        "document_type": "salary_slip",
        "facts": facts,
        "warnings": [],
        "confidence": 0.84,
    }
