def eligible(total_income: float, has_capital_gains: bool, resident: bool) -> bool:
    return resident and not has_capital_gains and total_income <= 5000000.0
