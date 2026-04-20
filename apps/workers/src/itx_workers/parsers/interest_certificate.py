def parse(raw_text: str) -> dict:
    return {"parser": "interest_certificate", "raw": raw_text[:200]}
