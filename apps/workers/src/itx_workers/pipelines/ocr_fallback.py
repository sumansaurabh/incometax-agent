from __future__ import annotations

from itx_workers.parsers.common import fallback_ocr_text


def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "ocr_fallback"
    content_bytes = payload.get("content_bytes")
    ocr_text = ""
    if content_bytes is not None:
        if isinstance(content_bytes, str):
            content_bytes = content_bytes.encode("utf-8")
        ocr_text = fallback_ocr_text(content_bytes)
    result["text"] = ocr_text
    result["ocr_used"] = bool(ocr_text)
    result["ocr_confidence"] = 0.35 if ocr_text else 0.0
    result["pages"] = [
        {
            "page_no": 1,
            "text": ocr_text,
            "ocr_used": bool(ocr_text),
            "ocr_confidence": 0.35 if ocr_text else 0.0,
        }
    ] if ocr_text else []
    return result
