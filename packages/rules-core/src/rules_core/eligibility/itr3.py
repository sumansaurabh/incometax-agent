def eligible(
    has_business_income: bool,
    presumptive_income: bool = False,
    partnership_income: bool = False,
) -> bool:
    return has_business_income and (partnership_income or not presumptive_income)