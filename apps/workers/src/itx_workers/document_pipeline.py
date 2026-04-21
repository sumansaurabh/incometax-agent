from __future__ import annotations

from typing import Any

from itx_workers.parsers import parse_document
from itx_workers.pipelines import classify, entities, normalize, ocr_fallback, table_extract, text_extract


async def process_document(payload: dict[str, Any]) -> dict[str, Any]:
    current = classify.run(payload)
    current = text_extract.run(current)
    current = table_extract.run(current)

    if not current.get("text"):
        current = ocr_fallback.run(current)

    parsed = parse_document(current.get("document_type", "unknown"), current.get("text", ""))
    current["parsed"] = parsed
    current = entities.run(current)
    current = normalize.run(current)
    current["processing_summary"] = {
        "document_type": current.get("document_type"),
        "classification_confidence": current.get("classification_confidence"),
        "text_extraction_confidence": current.get("text_extraction_confidence"),
        "ocr_used": current.get("ocr_used", False),
        "ocr_confidence": current.get("ocr_confidence"),
    }
    return current


__all__ = ["process_document"]