from __future__ import annotations

from itx_workers.parsers.common import extract_pdf_pages_from_bytes, fallback_ocr_text


def run(payload: dict) -> dict:
    result = dict(payload)
    result["stage"] = "ocr_fallback"
    content_bytes = payload.get("content_bytes")
    ocr_text = ""
    pages = []
    if content_bytes is not None:
        if isinstance(content_bytes, str):
            content_bytes = content_bytes.encode("utf-8")
        if content_bytes.startswith(b"%PDF"):
            pages = extract_pdf_pages_from_bytes(content_bytes, render_ocr=True)
            ocr_text = "\n\n".join(str(page.get("text") or "") for page in pages if page.get("text"))
        else:
            ocr_text = fallback_ocr_text(content_bytes)
    result["text"] = ocr_text
    result["ocr_used"] = bool(ocr_text)
    result["ocr_confidence"] = 0.35 if ocr_text else 0.0
    result["pages"] = pages or ([
        {
            "page_no": 1,
            "text": ocr_text,
            "ocr_used": bool(ocr_text),
            "ocr_confidence": 0.35 if ocr_text else 0.0,
        }
    ] if ocr_text else [])
    return result
