def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "entities"
    return result
