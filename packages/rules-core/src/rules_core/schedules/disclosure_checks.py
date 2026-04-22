def checks(
    has_foreign_assets: bool,
    has_crypto_activity: bool = False,
    has_unreported_interest: bool = False,
    uses_presumptive_scheme: bool = False,
    has_foreign_income: bool = False,
    is_director: bool = False,
    has_unlisted_equity: bool = False,
    agricultural_income: float = 0.0,
) -> list[str]:
    warnings = []
    if has_foreign_assets:
        warnings.append("Foreign asset disclosure required")
    if has_foreign_income:
        warnings.append("Foreign income disclosure should be reviewed before filing")
    if has_crypto_activity:
        warnings.append("Virtual digital asset disclosure required")
    if has_unreported_interest:
        warnings.append("Interest income mismatch should be reviewed before filing")
    if uses_presumptive_scheme:
        warnings.append("Presumptive taxation declarations must match the chosen ITR form")
    if is_director:
        warnings.append("Director details must be disclosed in the return")
    if has_unlisted_equity:
        warnings.append("Unlisted equity holdings must be disclosed in the return")
    if agricultural_income > 5000.0:
        warnings.append("Agricultural income above 5,000 should be disclosed for rate purposes")
    return warnings
