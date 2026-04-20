def parse(raw_text: str) -> dict:
    return {"parser": "ais_csv", "raw": raw_text[:200]}
