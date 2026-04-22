def eligible(
    has_capital_gains: bool,
    no_business_income: bool = True,
    resident: bool = True,
    total_income: float = 0.0,
    has_multiple_house_properties: bool = False,
    has_foreign_assets: bool = False,
    has_unlisted_equity: bool = False,
) -> bool:
    return no_business_income and (
        has_capital_gains
        or has_multiple_house_properties
        or has_foreign_assets
        or has_unlisted_equity
        or total_income > 5000000.0
        or not resident
    )
