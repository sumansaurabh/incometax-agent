def checks(
    has_foreign_assets: bool,
    has_crypto_activity: bool = False,
    has_unreported_interest: bool = False,
    uses_presumptive_scheme: bool = False,
) -> list[str]:
    warnings = []
    if has_foreign_assets:
        warnings.append("Foreign asset disclosure required")
    if has_crypto_activity:
        warnings.append("Virtual digital asset disclosure required")
    if has_unreported_interest:
        warnings.append("Interest income mismatch should be reviewed before filing")
    if uses_presumptive_scheme:
        warnings.append("Presumptive taxation declarations must match the chosen ITR form")
    return warnings
