from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount


def parse(raw_text: str) -> dict:
    interest = extract_labeled_amount(raw_text, ["Interest Certificate", "Interest on Housing Loan", "Interest Amount"])
    principal = extract_labeled_amount(raw_text, ["Principal Repaid", "Principal Amount"])
    facts = {
        "house_property": {"loan_interest": interest or 0.0, "net": -(interest or 0.0)},
        "deductions": {"80c": principal or 0.0},
    }
    return {
        "parser": "home_loan_cert",
        "document_type": "home_loan_cert",
        "facts": facts,
        "warnings": [],
        "confidence": 0.82,
    }
