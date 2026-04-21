from typing import List, Optional


def required(
    income_heads: List[str],
    has_business_income: bool = False,
    has_foreign_assets: bool = False,
    has_tax_payments: bool = False,
    has_deductions: bool = False,
) -> List[str]:
    schedule = []
    normalized_heads = set(income_heads)
    if "salary" in normalized_heads:
        schedule.append("Schedule S")
    if "capital_gains" in normalized_heads:
        schedule.append("Schedule CG")
    if "house_property" in normalized_heads:
        schedule.append("Schedule HP")
    if "other_sources" in normalized_heads:
        schedule.append("Schedule OS")
    if has_business_income or "business" in normalized_heads:
        schedule.append("Schedule BP")
    if has_deductions:
        schedule.append("Schedule VI-A")
    if has_tax_payments:
        schedule.append("Schedule TDS/TCS")
    if has_foreign_assets:
        schedule.append("Schedule FA")
    return schedule
