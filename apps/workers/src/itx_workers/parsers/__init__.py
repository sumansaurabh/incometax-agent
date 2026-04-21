from __future__ import annotations

from typing import Callable

from . import (
    ais_csv,
    ais_json,
    ais_pdf,
    broker_capgain,
    elss_ppf,
    form16,
    form16a,
    home_loan_cert,
    interest_certificate,
    rent_receipt,
    salary_slip,
    tis,
)


Parser = Callable[[str], dict]


PARSERS: dict[str, Parser] = {
    "ais_json": ais_json.parse,
    "ais_csv": ais_csv.parse,
    "ais_pdf": ais_pdf.parse,
    "tis": tis.parse,
    "form16": form16.parse,
    "form16a": form16a.parse,
    "salary_slip": salary_slip.parse,
    "interest_certificate": interest_certificate.parse,
    "rent_receipt": rent_receipt.parse,
    "home_loan_cert": home_loan_cert.parse,
    "elss_ppf": elss_ppf.parse,
    "broker_capgain": broker_capgain.parse,
}


def parse_document(document_type: str, raw_text: str) -> dict:
    parser = PARSERS.get(document_type)
    if parser is None:
        return {
            "parser": "unknown",
            "document_type": document_type,
            "facts": {},
            "warnings": [f"Unsupported document type: {document_type}"],
            "confidence": 0.25,
        }
    return parser(raw_text)


__all__ = ["PARSERS", "parse_document"]