def cap_80c(value: float) -> float:
    return min(value, 150000.0)


def cap_80d(value: float, senior_citizen: bool = False) -> float:
    return min(value, 50000.0 if senior_citizen else 25000.0)
