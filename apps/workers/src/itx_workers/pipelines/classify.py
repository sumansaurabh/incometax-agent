def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "classify"
    return result
