from __future__ import annotations

from itx_workers.parsers.common import (
    decode_text_bytes,
    extract_pdf_pages_from_bytes,
    extract_text_from_image_bytes,
    extract_text_from_pdf_bytes,
    normalize_text,
)


def run(payload: dict) -> dict:
    result = dict(payload)
    content_bytes = payload.get("content_bytes")
    mime_type = str(payload.get("mime_type") or payload.get("mime") or "").lower()
    file_name = str(payload.get("file_name") or "").lower()

    if content_bytes is not None:
        if isinstance(content_bytes, str):
            content_bytes = content_bytes.encode("utf-8")
        if mime_type == "application/pdf" or file_name.endswith(".pdf"):
            pages = extract_pdf_pages_from_bytes(content_bytes, render_ocr=True)
            text = normalize_text("\n\n".join(str(page.get("text") or "") for page in pages if page.get("text")))
            if not text:
                text = extract_text_from_pdf_bytes(content_bytes)
                pages = [
                    {
                        "page_no": 1,
                        "text": text,
                        "ocr_used": False,
                        "ocr_confidence": None,
                    }
                ] if text else []
            confidence = 0.72 if any(page.get("ocr_used") for page in pages) else (0.9 if text else 0.0)
            result["pages"] = pages
            result["ocr_used"] = any(bool(page.get("ocr_used")) for page in pages)
            result["ocr_confidence"] = max([float(page.get("ocr_confidence") or 0) for page in pages] or [0.0])
            result["text"] = text
            result["text_extraction_confidence"] = confidence
            result["stage"] = "text_extract"
            return result
        elif mime_type.startswith("image/") or file_name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff")):
            text = extract_text_from_image_bytes(content_bytes)
            confidence = 0.68 if text else 0.0
            result["ocr_used"] = bool(text)
            result["ocr_confidence"] = confidence
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
    result["pages"] = result.get("pages") or ([
        {
            "page_no": 1,
            "text": text,
            "ocr_used": bool(result.get("ocr_used", False)),
            "ocr_confidence": result.get("ocr_confidence"),
        }
    ] if text else [])
    result["text_extraction_confidence"] = confidence
    result["stage"] = "text_extract"
    return result
