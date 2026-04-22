from __future__ import annotations

import re

from itx_workers.parsers.common import (
    PAN_PATTERN,
    extract_assessment_year,
    extract_labeled_amount,
    extract_labeled_text,
    extract_nearby_amount,
    extract_pan,
    extract_tan,
    parse_indian_amount,
)


def _extract_employee_pan(raw_text: str) -> str | None:
    match = None
    for label in ("PAN of the Employee", "PAN of Employee", "Employee/Specified senior citizen"):
        label_match = re.search(label, raw_text, re.IGNORECASE)
        if not label_match:
            continue
        snippet = raw_text[label_match.end() : label_match.end() + 220]
        matches = PAN_PATTERN.findall(snippet)
        if matches:
            match = matches[-1]
            break
    return match or extract_pan(raw_text)


def _amounts_in_line(line: str) -> list[float]:
    values = re.findall(r"(?<![A-Z0-9])([0-9][0-9,]{2,}(?:\.[0-9]{1,2})?|[0-9]\.[0-9]{1,2})", line)
    amounts: list[float] = []
    for value in values:
        parsed = parse_indian_amount(value)
        if parsed is not None:
            amounts.append(parsed)
    return amounts


def _extract_tds_salary(raw_text: str) -> float | None:
    compact_text = re.sub(r"\s+", "", raw_text).upper()
    is_part_b_only = "PARTB" in compact_text and "PARTA" not in compact_text
    if is_part_b_only:
        return None

    for line in raw_text.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        amounts = _amounts_in_line(normalized)
        if len(amounts) >= 3 and (re.search(r"\bQ[1-4a]\b", normalized, re.IGNORECASE) or "Total (Rs.)" in normalized):
            return min(amounts)

    amount = extract_nearby_amount(
        raw_text,
        [
            "Amount of tax deducted",
            "Tax Deposited / Remitted",
        ],
        prefer="first",
    )
    if amount and amount >= 100:
        return amount
    return extract_labeled_amount(raw_text, ["Tax deducted at source", "TDS deducted"])


def parse(raw_text: str) -> dict:
    gross = (
        extract_nearby_amount(
            raw_text,
            [
                "Total amount of salary received from current employer",
                "Income chargeable under the head \"Salaries\"",
                "Salary as per provisions contained in section 17(1)",
                "Salary as per provisions contained u/s 17(1)",
            ],
            prefer="first",
        )
        or extract_labeled_amount(raw_text, ["Gross Salary", "Total Salary"])
    )
    tds_salary = _extract_tds_salary(raw_text)
    standard_deduction = extract_nearby_amount(raw_text, ["Standard deduction under section 16(ia)"], prefer="first")
    gross_total_income = extract_nearby_amount(raw_text, ["Gross total income"], prefer="first")
    taxable_income = extract_nearby_amount(raw_text, ["Total taxable income"], prefer="first")
    rebate_87a = extract_nearby_amount(raw_text, ["Rebate under section 87A"], prefer="first")
    tax_payable = extract_nearby_amount(raw_text, ["Net tax payable", "Tax payable"], prefer="first")
    facts = {
        "pan": _extract_employee_pan(raw_text),
        "name": extract_labeled_text(raw_text, ["Employee Name", "Name of Employee", "Name"]),
        "assessment_year": extract_assessment_year(raw_text),
        "employer_name": extract_labeled_text(raw_text, ["Employer Name", "Name and address of the employer"]),
        "employer_tan": extract_tan(raw_text),
        "salary": {"gross": gross or 0.0},
        "gross_total_income": gross_total_income or gross or 0.0,
        "standard_deduction": standard_deduction or 0.0,
        "taxable_income": taxable_income or 0.0,
        "rebate_87a": rebate_87a or 0.0,
        "tax_payable": tax_payable or 0.0,
        "tax_paid": {"tds_salary": tds_salary or 0.0, "tds_other": 0.0},
    }
    return {
        "parser": "form16",
        "document_type": "form16",
        "facts": facts,
        "warnings": [],
        "confidence": 0.91,
    }
