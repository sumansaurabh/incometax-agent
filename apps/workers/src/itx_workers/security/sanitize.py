def sanitize_text(value: str) -> str:
    return value.replace("\x00", "")
