from __future__ import annotations

import re
from typing import Any


PROMPT_INJECTION_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"(?im)^(system|assistant|developer)\s*:\s*", "role-directive", "high"),
    (r"(?im)ignore\s+(all\s+)?previous\s+instructions", "instruction-override", "high"),
    (r"(?im)tool\s*call|function\s*call|browser\s*automation", "tool-call-language", "medium"),
    (r"(?im)```(?:json|yaml|tool|function)?", "code-fence-directive", "medium"),
    (r"(?im)send\s+this\s+to\s+the\s+agent|execute\s+these\s+steps", "execution-language", "medium"),
)


def sanitize_text(value: str) -> str:
    cleaned = value.replace("\x00", "")
    return cleaned


def analyze_text_security(value: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    total_score = 0
    for pattern, code, severity in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, value):
            findings.append({"code": code, "severity": severity})
            total_score += 3 if severity == "high" else 1

    if total_score >= 3:
        risk = "high"
    elif total_score >= 1:
        risk = "medium"
    else:
        risk = "low"

    return {
        "prompt_injection_risk": risk,
        "findings": findings,
        "sanitized": sanitize_text(value) == value,
    }
