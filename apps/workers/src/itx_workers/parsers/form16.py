from __future__ import annotations

from itx_workers.parsers.common import (
    extract_assessment_year,
    extract_labeled_amount,
    extract_labeled_text,
    extract_pan,
    extract_tan,
)


def parse(raw_text: str) -> dict:
    gross = extract_labeled_amount(raw_text, ["Gross Salary", "Salary as per provisions contained u/s 17(1)", "Total Salary"])
    tds_salary = extract_labeled_amount(raw_text, ["Tax deducted at source", "TDS deducted", "Tax Deposited / Remitted"])
    facts = {
        "pan": extract_pan(raw_text),
        "name": extract_labeled_text(raw_text, ["Employee Name", "Name of Employee", "Name"]),
        "assessment_year": extract_assessment_year(raw_text),
        "employer_name": extract_labeled_text(raw_text, ["Employer Name", "Name and address of the employer"]),
        "employer_tan": extract_tan(raw_text),
        "salary": {"gross": gross or 0.0},
        "tax_paid": {"tds_salary": tds_salary or 0.0, "tds_other": 0.0},
    }
    return {
        "parser": "form16",
        "document_type": "form16",
        "facts": facts,
        "warnings": [],
        "confidence": 0.91,
    }
