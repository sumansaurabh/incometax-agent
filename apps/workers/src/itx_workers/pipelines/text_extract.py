def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "text_extract"
    return result
