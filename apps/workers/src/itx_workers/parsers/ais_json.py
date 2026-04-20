def parse(raw_text: str) -> dict:
    return {"parser": "ais_json", "raw": raw_text[:200]}
