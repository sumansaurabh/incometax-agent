def eligible(
    presumptive_income: bool,
    total_income: float = 0.0,
    resident: bool = True,
    has_foreign_assets: bool = False,
    turnover: float = 0.0,
) -> bool:
    return presumptive_income and resident and not has_foreign_assets and total_income <= 5000000.0 and turnover <= 20000000.0
