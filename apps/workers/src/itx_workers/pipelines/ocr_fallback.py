from __future__ import annotations


def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "ocr_fallback"
    result.setdefault("ocr_used", False)
    result.setdefault("ocr_confidence", None)
    return result
