from __future__ import annotations

from itx_workers.parsers.common import normalize_text


def run(payload: dict) -> dict:
    result = dict(payload)
    raw_text = payload.get("raw_text") or payload.get("text") or ""
    result["text"] = normalize_text(str(raw_text))
    result["stage"] = "text_extract"
    return result
