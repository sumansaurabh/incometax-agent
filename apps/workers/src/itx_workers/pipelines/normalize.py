from __future__ import annotations

from typing import Any


def _merge_dict(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = _merge_dict(dict(target[key]), value)
        else:
            target[key] = value
    return target


def _coerce_to_tax_facts(parsed_facts: dict[str, Any]) -> dict[str, Any]:
    tax_facts: dict[str, Any] = {}

    for key in ("pan", "assessment_year", "name", "dob", "residential_status", "regime"):
        value = parsed_facts.get(key)
        if value is not None:
            tax_facts[key] = value

    nested_keys = [
        "salary",
        "tax_paid",
        "deductions",
        "other_sources",
        "capital_gains",
        "bank",
        "house_property",
        "exemptions",
    ]
    for key in nested_keys:
        value = parsed_facts.get(key)
        if isinstance(value, dict) and value:
            tax_facts[key] = value

    if parsed_facts.get("salary", {}).get("gross"):
        tax_facts["gross_salary"] = parsed_facts["salary"]["gross"]
        tax_facts["has_salary_income"] = True

    if parsed_facts.get("employer_name"):
        tax_facts["employer_name"] = parsed_facts["employer_name"]
    if parsed_facts.get("employer_tan"):
        tax_facts["employer_tan"] = parsed_facts["employer_tan"]
    if parsed_facts.get("father_name"):
        tax_facts["father_name"] = parsed_facts["father_name"]

    salary_total = float(parsed_facts.get("salary", {}).get("gross", 0) or 0)
    house_total = float(parsed_facts.get("house_property", {}).get("net", 0) or 0)
    other_total = float(parsed_facts.get("other_sources", {}).get("total", 0) or 0)
    capital = parsed_facts.get("capital_gains", {})
    capital_total = float(capital.get("stcg", 0) or 0) + float(capital.get("ltcg", 0) or 0)
    total_income = salary_total + house_total + other_total + capital_total
    if total_income:
        tax_facts["total_income"] = total_income

    return tax_facts


def run(payload: dict) -> dict:
    result = dict(payload)
    parsed = payload.get("parsed", {})
    parsed_facts = parsed.get("facts", {})
    result["normalized_fields"] = _coerce_to_tax_facts(parsed_facts)
    result["normalization_schema_version"] = "phase2-doc-intel-1"
    result["stage"] = "normalize"
    return result
