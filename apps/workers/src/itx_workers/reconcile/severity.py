def severity(diff_amount: float) -> str:
    if diff_amount < 100:
        return "harmless"
    if diff_amount < 1000:
        return "missing-doc"
    return "human-decision"
