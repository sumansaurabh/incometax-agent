def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "table_extract"
    return result
