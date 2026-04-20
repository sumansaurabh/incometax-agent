def parse(raw_text: str) -> dict:
    return {"parser": "broker_capgain", "raw": raw_text[:200]}
