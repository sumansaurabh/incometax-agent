def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "normalize"
    return result
