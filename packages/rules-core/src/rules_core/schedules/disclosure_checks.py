def checks(has_foreign_assets: bool) -> list[str]:
    warnings = []
    if has_foreign_assets:
        warnings.append("Foreign asset disclosure required")
    return warnings
