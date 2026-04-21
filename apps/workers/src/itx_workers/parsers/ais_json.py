from __future__ import annotations

from itx_workers.parsers.common import deep_find, parse_indian_amount, parse_json_document


def parse(raw_text: str) -> dict:
    data = parse_json_document(raw_text)

    salary = parse_indian_amount(deep_find(data, ["grossSalary", "gross_salary", "salaryGross", "salary_amount"]))
    tds_salary = parse_indian_amount(deep_find(data, ["tdsSalary", "tds_salary"]))
    tds_other = parse_indian_amount(deep_find(data, ["tdsOther", "tds_other"]))
    other_sources = parse_indian_amount(deep_find(data, ["otherSources", "other_sources", "interestIncome", "interest_income"]))
    stcg = parse_indian_amount(deep_find(data, ["stcg", "shortTermCapitalGain", "short_term_capital_gain"]))
    ltcg = parse_indian_amount(deep_find(data, ["ltcg", "longTermCapitalGain", "long_term_capital_gain"]))
    section_80c = parse_indian_amount(deep_find(data, ["section80C", "section_80c", "deduction80C", "deduction_80c"]))
    section_80d = parse_indian_amount(deep_find(data, ["section80D", "section_80d", "deduction80D", "deduction_80d"]))

    facts = {
        "pan": deep_find(data, ["pan", "panNumber", "pan_number"]),
        "name": deep_find(data, ["fullName", "full_name", "taxpayerName", "name"]),
        "assessment_year": deep_find(data, ["assessmentYear", "assessment_year", "ay"]),
        "salary": {"gross": salary or 0.0},
        "tax_paid": {
            "tds_salary": tds_salary or 0.0,
            "tds_other": tds_other or 0.0,
        },
        "other_sources": {"total": other_sources or 0.0},
        "capital_gains": {"stcg": stcg or 0.0, "ltcg": ltcg or 0.0},
        "deductions": {"80c": section_80c or 0.0, "80d": section_80d or 0.0},
        "bank": {
            "ifsc": deep_find(data, ["ifsc", "ifscCode", "ifsc_code"]),
            "account_number": deep_find(data, ["accountNumber", "account_number", "refundAccountNumber"]),
            "name": deep_find(data, ["bankName", "bank_name"]),
        },
    }

    return {
        "parser": "ais_json",
        "document_type": "ais_json",
        "facts": facts,
        "warnings": [],
        "confidence": 0.93,
    }
