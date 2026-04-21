from __future__ import annotations

from typing import Any


def flatten_tax_facts(prefix: str, value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        out: list[tuple[str, Any]] = []
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            out.extend(flatten_tax_facts(child_prefix, child))
        return out
    return [(prefix, value)]