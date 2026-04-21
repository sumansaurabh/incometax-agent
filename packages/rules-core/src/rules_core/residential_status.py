from typing import Dict


def classify(
    days_in_india: int,
    days_in_prev_four_years: int = 0,
    days_in_prev_seven_years: int = 0,
    liable_to_tax_elsewhere: bool = True,
) -> Dict[str, object]:
    if days_in_india >= 182 or (days_in_india >= 60 and days_in_prev_four_years >= 365):
        resident = True
    else:
        resident = False

    if not resident:
        return {
            "status": "nr",
            "resident": False,
            "reason": "day_count_threshold_not_met",
        }

    if days_in_prev_seven_years >= 730 and liable_to_tax_elsewhere:
        return {
            "status": "resident",
            "resident": True,
            "reason": "resident_and_ordinary_resident",
        }

    return {
        "status": "rnor",
        "resident": True,
        "reason": "resident_but_not_ordinary_resident",
    }