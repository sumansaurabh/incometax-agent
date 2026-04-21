from typing import Any, Dict, List, Optional

from rules_core.caps.chapter_vi_a import cap_80c, cap_80d, cap_80g, cap_80tta, cap_80ttb, hra_exemption
from rules_core.caps.standard_deduction import standard_deduction
from rules_core.eligibility.itr1 import eligible as itr1_eligible
from rules_core.eligibility.itr2 import eligible as itr2_eligible
from rules_core.eligibility.itr3 import eligible as itr3_eligible
from rules_core.eligibility.itr4 import eligible as itr4_eligible
from rules_core.regime.old_vs_new import compare
from rules_core.residential_status import classify as classify_residential_status
from rules_core.schedules.disclosure_checks import checks as disclosure_checks
from rules_core.schedules.required_schedules import required as required_schedules


def evaluate(
    deductions_80c: float,
    deductions_80d: float,
    is_salary: bool,
    old_tax: float,
    new_tax: float,
    *,
    total_income: float = 0.0,
    has_capital_gains: bool = False,
    resident: bool = True,
    has_business_income: bool = False,
    presumptive_income: bool = False,
    partnership_income: bool = False,
    senior_citizen: bool = False,
    donations_80g: float = 0.0,
    donation_qualifying_percent: float = 0.5,
    donation_qualifying_limit: float = 0.0,
    savings_interest: float = 0.0,
    senior_interest: float = 0.0,
    hra_received: float = 0.0,
    rent_paid: float = 0.0,
    basic_salary: float = 0.0,
    metro: bool = False,
    income_heads: Optional[List[str]] = None,
    has_foreign_assets: bool = False,
    has_multiple_house_properties: bool = False,
    has_tax_payments: bool = False,
    days_in_india: Optional[int] = None,
    days_in_prev_four_years: int = 0,
    days_in_prev_seven_years: int = 0,
    liable_to_tax_elsewhere: bool = True,
    has_crypto_activity: bool = False,
    has_unreported_interest: bool = False,
) -> Dict[str, Any]:
    inferred_income_heads = list(income_heads or [])
    if is_salary and "salary" not in inferred_income_heads:
        inferred_income_heads.append("salary")
    if has_capital_gains and "capital_gains" not in inferred_income_heads:
        inferred_income_heads.append("capital_gains")
    if has_business_income and "business" not in inferred_income_heads:
        inferred_income_heads.append("business")

    residential_status = (
        classify_residential_status(
            days_in_india=days_in_india,
            days_in_prev_four_years=days_in_prev_four_years,
            days_in_prev_seven_years=days_in_prev_seven_years,
            liable_to_tax_elsewhere=liable_to_tax_elsewhere,
        )
        if days_in_india is not None
        else {
            "status": "resident" if resident else "nr",
            "resident": resident,
            "reason": "explicit_resident_flag",
        }
    )

    deductions = {
        "section_80c_applied": cap_80c(deductions_80c),
        "section_80d_applied": cap_80d(deductions_80d, senior_citizen=senior_citizen),
        "section_80g_applied": cap_80g(
            donations_80g,
            qualifying_percent=donation_qualifying_percent,
            qualifying_limit=donation_qualifying_limit,
        ),
        "section_80tta_applied": cap_80tta(savings_interest),
        "section_80ttb_applied": cap_80ttb(senior_interest),
        "hra_exemption_applied": hra_exemption(hra_received, rent_paid, basic_salary, metro=metro),
    }
    deductions_present = any(value > 0 for value in deductions.values())

    return {
        "section_80c_applied": deductions["section_80c_applied"],
        "section_80d_applied": deductions["section_80d_applied"],
        "standard_deduction": standard_deduction(is_salary),
        "regime": compare(old_tax, new_tax),
        "deductions": deductions,
        "residential_status": residential_status,
        "eligibility": {
            "itr1": itr1_eligible(total_income, has_capital_gains, bool(residential_status["resident"])),
            "itr2": itr2_eligible(
                has_capital_gains,
                no_business_income=not has_business_income,
                resident=bool(residential_status["resident"]),
                total_income=total_income,
                has_multiple_house_properties=has_multiple_house_properties,
                has_foreign_assets=has_foreign_assets,
            ),
            "itr3": itr3_eligible(
                has_business_income=has_business_income,
                presumptive_income=presumptive_income,
                partnership_income=partnership_income,
            ),
            "itr4": itr4_eligible(
                presumptive_income=presumptive_income,
                total_income=total_income,
                resident=bool(residential_status["resident"]),
                has_foreign_assets=has_foreign_assets,
                turnover=total_income,
            ),
        },
        "required_schedules": required_schedules(
            inferred_income_heads,
            has_business_income=has_business_income,
            has_foreign_assets=has_foreign_assets,
            has_tax_payments=has_tax_payments,
            has_deductions=deductions_present,
        ),
        "disclosure_checks": disclosure_checks(
            has_foreign_assets=has_foreign_assets,
            has_crypto_activity=has_crypto_activity,
            has_unreported_interest=has_unreported_interest,
            uses_presumptive_scheme=presumptive_income,
        ),
    }
