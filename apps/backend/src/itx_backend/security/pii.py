import re
from typing import Any

PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_PATTERN = re.compile(r"\b[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b")


def redact_text(value: str) -> str:
    redacted = PAN_PATTERN.sub("[PAN_REDACTED]", value)
    redacted = AADHAAR_PATTERN.sub("[AADHAAR_REDACTED]", redacted)
    return redacted


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: redact_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [redact_payload(v) for v in payload]
    if isinstance(payload, str):
        return redact_text(payload)
    return payload
