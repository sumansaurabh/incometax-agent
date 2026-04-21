from __future__ import annotations


def severity(diff_amount: float, *, reference_amount: float = 0.0, category: str = "generic") -> str:
    baseline = max(abs(reference_amount), 1.0)
    diff_ratio = abs(diff_amount) / baseline

    if category == "duplicate":
        return "warning"
    if category == "prefill_issue":
        return "warning"
    if diff_ratio < 0.03 or abs(diff_amount) < 100:
        return "info"
    if category == "missing-doc" or diff_ratio < 0.1 or abs(diff_amount) < 1000:
        return "warning"
    return "error"
