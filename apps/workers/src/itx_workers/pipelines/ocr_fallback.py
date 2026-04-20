def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "ocr_fallback"
    return result
