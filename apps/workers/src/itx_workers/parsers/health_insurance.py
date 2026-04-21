from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount, extract_labeled_text


def parse(raw_text: str) -> dict:
    self_family = extract_labeled_amount(
        raw_text,
        ["Self and Family Premium", "Self/Family Premium", "Health Insurance Premium", "Mediclaim Premium"],
    )
    parents = extract_labeled_amount(
        raw_text,
        ["Parents Premium", "Premium for Parents", "Senior Citizen Parents Premium"],
    )
    total = (self_family or 0.0) + (parents or 0.0)
    facts = {
        "name": extract_labeled_text(raw_text, ["Policy Holder", "Insured Name", "Name"]),
        "deductions": {
            "80d": total,
            "80d_parents": parents or 0.0,
        },
    }
    return {
        "parser": "health_insurance",
        "document_type": "health_insurance",
        "facts": facts,
        "warnings": [],
        "confidence": 0.84,
    }