def parse(raw_text: str) -> dict:
    return {"parser": "rent_receipt", "raw": raw_text[:200]}
