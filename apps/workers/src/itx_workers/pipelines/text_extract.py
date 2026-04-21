from __future__ import annotations

from itx_workers.parsers.common import decode_text_bytes, extract_text_from_pdf_bytes, normalize_text


def run(payload: dict) -> dict:
    result = dict(payload)
    content_bytes = payload.get("content_bytes")
    mime_type = str(payload.get("mime_type") or payload.get("mime") or "").lower()
    file_name = str(payload.get("file_name") or "").lower()

    if content_bytes is not None:
        if isinstance(content_bytes, str):
            content_bytes = content_bytes.encode("utf-8")
        if mime_type == "application/pdf" or file_name.endswith(".pdf"):
            text = extract_text_from_pdf_bytes(content_bytes)
            confidence = 0.82 if text else 0.0
        elif mime_type in {"application/json", "text/csv", "text/plain"} or file_name.endswith((".json", ".csv", ".txt")):
            text = normalize_text(decode_text_bytes(content_bytes))
            confidence = 0.99 if text else 0.0
        else:
            text = normalize_text(decode_text_bytes(content_bytes))
            confidence = 0.72 if text else 0.0
    else:
        raw_text = payload.get("raw_text") or payload.get("text") or ""
        text = normalize_text(str(raw_text))
        confidence = 0.95 if text else 0.0

    result["text"] = text
    result["pages"] = [
        {
            "page_no": 1,
            "text": text,
            "ocr_used": False,
            "ocr_confidence": None,
        }
    ] if text else []
    result["text_extraction_confidence"] = confidence
    result["stage"] = "text_extract"
    return result
