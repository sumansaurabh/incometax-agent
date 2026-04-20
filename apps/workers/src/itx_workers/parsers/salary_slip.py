def parse(raw_text: str) -> dict:
    return {"parser": "salary_slip", "raw": raw_text[:200]}
