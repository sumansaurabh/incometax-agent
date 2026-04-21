from __future__ import annotations

import json
from typing import Any


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def remove_duplicates(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        key = json.dumps(_canonicalize(row), sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def find_duplicate_documents(rows: list[dict]) -> list[dict]:
    seen: dict[tuple[str, str], dict] = {}
    duplicates: list[dict] = []
    for row in rows:
        identity = (str(row.get("type") or "unknown"), str(row.get("sha256") or row.get("fingerprint") or ""))
        if not identity[1]:
            continue
        if identity in seen:
            duplicates.append(
                {
                    "field": "document",
                    "severity": "warning",
                    "category": "duplicate",
                    "description": f"Duplicate {identity[0]} proof uploaded.",
                    "document_id": row.get("id"),
                    "duplicate_of": seen[identity].get("id"),
                }
            )
            continue
        seen[identity] = row
    return duplicates
