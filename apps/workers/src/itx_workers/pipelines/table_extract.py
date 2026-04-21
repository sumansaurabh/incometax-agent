from __future__ import annotations

from itx_workers.parsers.common import parse_csv_rows


def run(payload: dict) -> dict:
    result = dict(payload)
    if result.get("document_type") == "ais_csv" and result.get("text"):
        result["tables"] = [parse_csv_rows(result["text"])]
    else:
        result["tables"] = result.get("tables", [])
    result["stage"] = "table_extract"
    return result
