def classify(amount_delta: float) -> str:
    if amount_delta < 100:
        return "harmless"
    if amount_delta < 1000:
        return "missing-doc"
    return "human-decision"
