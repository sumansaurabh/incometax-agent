from __future__ import annotations


ALIASES = {
    "ais": "ais_pdf",
    "ais json": "ais_json",
    "ais csv": "ais_csv",
    "broker_statement": "broker_capgain",
    "broker_capital_gain": "broker_capgain",
    "form_16": "form16",
    "form_16a": "form16a",
    "salary-slip": "salary_slip",
    "interest-certificate": "interest_certificate",
    "home-loan-certificate": "home_loan_cert",
}


def _detect_from_payload(payload: dict) -> tuple[str, float]:
    declared = str(payload.get("doc_type") or payload.get("document_type") or "").strip().lower().replace("-", "_")
    if declared:
        return ALIASES.get(declared, declared), 0.99

    file_name = str(payload.get("file_name") or "").lower()
    mime_type = str(payload.get("mime_type") or payload.get("mime") or "").lower()
    text = str(payload.get("raw_text") or payload.get("text") or "").lower()

    if mime_type == "application/json" or file_name.endswith(".json"):
        return "ais_json", 0.92
    if mime_type == "text/csv" or file_name.endswith(".csv"):
        return "ais_csv", 0.92
    if "form 16a" in text:
        return "form16a", 0.94
    if "form 16" in text:
        return "form16", 0.94
    if "tax information statement" in text or "tis" in text:
        return "tis", 0.88
    if "annual information statement" in text or "ais" in text:
        return "ais_pdf", 0.88
    if "salary slip" in text or "payslip" in text:
        return "salary_slip", 0.86
    if "health insurance" in text or "mediclaim" in text or "policy premium" in text:
        return "health_insurance", 0.86
    if "interest certificate" in text:
        return "interest_certificate", 0.86
    if "capital gain" in text or "contract note" in text or "broker" in text:
        return "broker_capgain", 0.82
    if "home loan" in text or "interest certificate" in text and "principal" in text:
        return "home_loan_cert", 0.80
    if "rent receipt" in text:
        return "rent_receipt", 0.80
    if "ppf" in text or "elss" in text or "lic premium" in text:
        return "elss_ppf", 0.78
    return "unknown", 0.25


def run(payload: dict) -> dict:
    result = dict(payload)
    document_type, confidence = _detect_from_payload(payload)
    result["stage"] = "classify"
    result["document_type"] = document_type
    result["classification_confidence"] = confidence
    return result
