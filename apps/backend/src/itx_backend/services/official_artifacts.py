from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional


def _normalized_fields(portal_state: Optional[dict[str, Any]]) -> list[dict[str, str]]:
    fields = (portal_state or {}).get("fields", {}) or {}
    items: list[dict[str, str]] = []
    for selector, raw in fields.items():
        if isinstance(raw, dict):
            value = raw.get("value")
            label = raw.get("label") or raw.get("fieldKey") or selector
            field_key = raw.get("fieldKey") or selector
        else:
            value = raw
            label = selector
            field_key = selector
        if value in (None, "", [], {}):
            continue
        items.append(
            {
                "selector": str(selector),
                "field_key": str(field_key),
                "label": str(label),
                "value": str(value),
            }
        )
    return items


def _find_field_value(fields: list[dict[str, str]], patterns: tuple[str, ...]) -> Optional[str]:
    for item in fields:
        haystack = f"{item['field_key']} {item['label']} {item['selector']}".lower()
        if any(pattern in haystack for pattern in patterns):
            return item["value"]
    return None


def _extract_with_regex(text: Optional[str], pattern: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def prepare_official_artifact_attachment(
    *,
    artifact_kind: str,
    page_type: Optional[str],
    page_title: Optional[str],
    page_url: Optional[str],
    portal_state: Optional[dict[str, Any]],
    manual_text: Optional[str],
    ack_no: Optional[str],
    portal_ref: Optional[str],
    filed_at: Optional[str],
) -> dict[str, Any]:
    normalized_kind = artifact_kind.strip().lower()
    if normalized_kind != "itr_v":
        raise ValueError("unsupported_artifact_kind")

    fields = _normalized_fields(portal_state)
    manual_text_value = (manual_text or "").strip() or None
    ack_value = (
        (ack_no or "").strip()
        or _find_field_value(fields, ("ack", "acknowledg", "filing number", "itrv_ack"))
        or _extract_with_regex(manual_text_value, r"ack(?:nowledg(?:ement|ment))?(?:\s*(?:number|no))?\s*[:#-]?\s*([A-Z0-9\-/]+)")
    )
    portal_ref_value = (
        (portal_ref or "").strip()
        or _find_field_value(fields, ("portal_ref", "reference", "transaction", "evc", "filing reference"))
        or _extract_with_regex(manual_text_value, r"(?:portal|transaction|reference|evc)(?:\s*(?:number|no|id|ref))?\s*[:#-]?\s*([A-Z0-9\-/]+)")
    )
    filed_at_value = (filed_at or "").strip() or _find_field_value(
        fields,
        ("filed_at", "ack_date", "acknowledgement date", "date of filing", "filing date"),
    )

    if not manual_text_value and not fields and not page_title and not page_url:
        raise ValueError("official_artifact_empty")

    content_lines = [
        "# Official Filing Artifact",
        "",
        f"Artifact Kind: {normalized_kind.upper()}",
        f"Captured At: {datetime.now(timezone.utc).isoformat()}",
        f"Page Type: {page_type or 'unknown'}",
        f"Page Title: {page_title or 'unknown'}",
        f"Page URL: {page_url or 'unknown'}",
        f"Acknowledgement Number: {ack_value or 'not found'}",
        f"Portal Reference: {portal_ref_value or 'not found'}",
        f"Filed At: {filed_at_value or 'not found'}",
        "",
        "## Captured Fields",
    ]
    if fields:
        content_lines.extend(f"- {item['label']}: {item['value']}" for item in fields)
    else:
        content_lines.append("- No structured portal fields were captured.")

    content_lines.extend(["", "## Captured Text"])
    content_lines.append(manual_text_value or "No pasted portal text was provided.")

    return {
        "artifact_kind": normalized_kind,
        "ack_no": ack_value or None,
        "portal_ref": portal_ref_value or None,
        "filed_at": filed_at_value or None,
        "content": "\n".join(content_lines),
        "metadata": {
            "page_type": page_type,
            "page_title": page_title,
            "page_url": page_url,
            "captured_fields": fields,
        },
    }