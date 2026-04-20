def required(income_heads: list[str]) -> list[str]:
    schedule = []
    if "salary" in income_heads:
        schedule.append("Schedule S")
    if "capital_gains" in income_heads:
        schedule.append("Schedule CG")
    if "house_property" in income_heads:
        schedule.append("Schedule HP")
    return schedule
