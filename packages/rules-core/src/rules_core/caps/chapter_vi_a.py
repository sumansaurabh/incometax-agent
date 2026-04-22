def cap_80c(value: float) -> float:
    return min(value, 150000.0)


def cap_80d(value: float, senior_citizen: bool = False) -> float:
    return min(value, 50000.0 if senior_citizen else 25000.0)


def cap_80g(value: float, qualifying_percent: float = 0.5, qualifying_limit: float = 0.0) -> float:
    eligible = max(value, 0.0) * qualifying_percent
    if qualifying_limit > 0:
        eligible = min(eligible, qualifying_limit)
    return eligible


def cap_80tta(value: float) -> float:
    return min(max(value, 0.0), 10000.0)


def cap_80ttb(value: float) -> float:
    return min(max(value, 0.0), 50000.0)


def cap_80e(value: float) -> float:
    return max(value, 0.0)


def cap_80ee(value: float) -> float:
    return min(max(value, 0.0), 50000.0)


def cap_80eea(value: float) -> float:
    return min(max(value, 0.0), 150000.0)


def cap_80gg(rent_paid: float, adjusted_total_income: float) -> float:
    income = max(adjusted_total_income, 0.0)
    return min(max(rent_paid - (0.10 * income), 0.0), 60000.0, 0.25 * income)


def hra_exemption(hra_received: float, rent_paid: float, salary: float, metro: bool = False) -> float:
    actual_hra = max(hra_received, 0.0)
    rent_minus_ten_percent = max(rent_paid - (0.10 * max(salary, 0.0)), 0.0)
    salary_percentage = 0.50 * max(salary, 0.0) if metro else 0.40 * max(salary, 0.0)
    return min(actual_hra, rent_minus_ten_percent, salary_percentage)
