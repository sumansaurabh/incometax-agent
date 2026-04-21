from __future__ import annotations

from itx_workers.parsers.common import aggregate_csv_amount, parse_csv_rows


def parse(raw_text: str) -> dict:
    rows = parse_csv_rows(raw_text)
    facts = {
        "salary": {"gross": aggregate_csv_amount(rows, ["salary", "gross salary"])},
        "tax_paid": {
            "tds_salary": aggregate_csv_amount(rows, ["tds salary", "tds on salary", "192"]),
            "tds_other": aggregate_csv_amount(rows, ["tds other", "interest", "194a", "194h", "194j"]),
        },
        "other_sources": {"total": aggregate_csv_amount(rows, ["interest", "other sources", "dividend"])},
        "capital_gains": {
            "stcg": aggregate_csv_amount(rows, ["stcg", "short term capital"]),
            "ltcg": aggregate_csv_amount(rows, ["ltcg", "long term capital"]),
        },
    }
    return {
        "parser": "ais_csv",
        "document_type": "ais_csv",
        "facts": facts,
        "rows": rows,
        "warnings": [],
        "confidence": 0.88,
    }
