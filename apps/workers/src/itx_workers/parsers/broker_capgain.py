from __future__ import annotations

from itx_workers.parsers.common import extract_labeled_amount


def parse(raw_text: str) -> dict:
    stcg = extract_labeled_amount(raw_text, ["Short Term Capital Gain", "STCG"])
    ltcg = extract_labeled_amount(raw_text, ["Long Term Capital Gain", "LTCG"])
    facts = {
        "capital_gains": {"stcg": stcg or 0.0, "ltcg": ltcg or 0.0},
    }
    return {
        "parser": "broker_capgain",
        "document_type": "broker_capgain",
        "facts": facts,
        "warnings": [],
        "confidence": 0.85,
    }
