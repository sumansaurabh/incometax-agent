def eligible(
    total_income: float,
    has_capital_gains: bool,
    resident: bool,
    has_multiple_house_properties: bool = False,
    has_foreign_assets: bool = False,
    has_business_income: bool = False,
    agricultural_income: float = 0.0,
) -> bool:
    return (
        resident
        and not has_capital_gains
        and total_income <= 5000000.0
        and not has_multiple_house_properties
        and not has_foreign_assets
        and not has_business_income
        and agricultural_income <= 5000.0
    )
