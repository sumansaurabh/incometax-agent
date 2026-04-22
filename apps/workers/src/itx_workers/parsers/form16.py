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


IDENTITY_BLOCK_STOP_MARKERS = (
    "PAN OF THE",
    "THE COMMISSIONER",
    "SUMMARY OF AMOUNT",
    "ANNEXURE",
    "RECEIPT NUMBERS",
    "CERTIFICATE NUMBER",
)

NON_NAME_TOKENS = {
    "APTUSDATALABS",
    "BANGALORE",
    "BUSINESSPARKS",
    "DEPARTMENT",
    "DIRECTOR",
    "EMPLOYEE",
    "EMPLOYER",
    "GANJ",
    "GOVERNMENT",
    "HOBLI",
    "INCOME",
    "KARNATAKA",
    "LIMITED",
    "LUCKNOW",
    "MAQBOOL",
    "OFFICE",
    "PARK",
    "PLTD",
    "PRIVATE",
    "PRADESH",
    "ROAD",
    "SPECIFIED",
    "TAX",
    "TECHNOLOGIES",
    "UTTAR",
    "VILLAG",
}


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", " ")).strip(" ,:-|")


def _clean_identity_value(value: str | None, *, require_no_digits: bool = False) -> str | None:
    if not value:
        return None
    candidate = _normalize_line(value)
    if not candidate:
        return None
    upper = candidate.upper()
    if any(
        token in upper
        for token in (
            "NAME AND ADDRESS",
            "PAN OF",
            "TAN OF",
            "ASSESSMENT YEAR",
            "CERTIFICATE NO",
            "INCOME TAX DEPARTMENT",
        )
    ):
        return None
    if "@" in candidate or candidate.startswith("+"):
        return None
    if require_no_digits and any(char.isdigit() for char in candidate):
        return None
    return candidate


def _extract_identity_block(raw_text: str) -> list[str]:
    lines = [_normalize_line(line) for line in raw_text.splitlines()]
    for index, line in enumerate(lines):
        upper = line.upper()
        if "NAME AND ADDRESS OF THE EMPLOYER" not in upper or "EMPLOYEE" not in upper:
            continue
        block: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate:
                if block:
                    break
                continue
            upper_candidate = candidate.upper()
            if any(marker in upper_candidate for marker in IDENTITY_BLOCK_STOP_MARKERS):
                break
            block.append(candidate)
            if len(block) >= 6:
                break
        return block
    return []


def _looks_like_person_name(value: str | None) -> bool:
    candidate = _clean_identity_value(value, require_no_digits=True)
    if not candidate:
        return False
    words = [word for word in candidate.replace(".", " ").split() if word]
    if not 2 <= len(words) <= 5:
        return False
    upper_words = {word.upper().strip("-'") for word in words}
    if upper_words & NON_NAME_TOKENS:
        return False
    return True


def _extract_employee_name(raw_text: str) -> str | None:
    labeled = _clean_identity_value(extract_labeled_text(raw_text, ["Employee Name", "Name of Employee"]), require_no_digits=True)
    if _looks_like_person_name(labeled):
        return labeled

    block = _extract_identity_block(raw_text)
    search_lines = block[2:] if len(block) >= 3 else block[1:]
    for line in search_lines:
        for part in reversed(line.split(",")):
            candidate = _clean_identity_value(part, require_no_digits=True)
            if _looks_like_person_name(candidate):
                return candidate
    return None


def _extract_employer_name(raw_text: str) -> str | None:
    labeled = _clean_identity_value(extract_labeled_text(raw_text, ["Employer Name"]))
    if labeled:
        return labeled

    block = _extract_identity_block(raw_text)
    if block:
        return _clean_identity_value(block[0])
    return None


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
        "name": _extract_employee_name(raw_text),
        "assessment_year": extract_assessment_year(raw_text),
        "employer_name": _extract_employer_name(raw_text),
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
