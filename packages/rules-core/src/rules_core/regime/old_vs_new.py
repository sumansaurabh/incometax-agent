def compare(old_tax: float, new_tax: float) -> dict:
    preferred = "old" if old_tax <= new_tax else "new"
    return {
        "old_tax": old_tax,
        "new_tax": new_tax,
        "preferred": preferred,
        "delta": abs(old_tax - new_tax)
    }
