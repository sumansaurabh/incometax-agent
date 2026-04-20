from itx_backend.security.pii import redact_payload


def safe_log_payload(payload: dict) -> dict:
    return redact_payload(payload)
