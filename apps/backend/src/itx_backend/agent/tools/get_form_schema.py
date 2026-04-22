from __future__ import annotations

from typing import Any, Optional

from itx_backend.agent.nodes.fill_plan import FIELD_MAPPINGS
from itx_backend.agent.tool_registry import tool_registry


_PAGE_TYPES = sorted(FIELD_MAPPINGS.keys())


@tool_registry.tool(
    name="get_form_schema",
    description=(
        "Return the canonical field schema for an e-Filing portal page: field ids, labels, CSS "
        "selectors, and the tax-fact key each field maps to. Use this when the user asks 'which "
        "fields are on this page?', or when you need to plan a fill operation before calling "
        "propose_fill. If page_type is omitted, returns the schema for every known page. Each "
        "field entry has {field_id, label, selector, maps_to_tax_fact}. The page_type must be one "
        "of: " + ", ".join(_PAGE_TYPES) + "."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "page_type": {
                "type": "string",
                "enum": _PAGE_TYPES,
                "description": "Optional page to restrict the schema. Omit for all pages.",
            },
        },
        "additionalProperties": False,
    },
)
async def get_form_schema(
    *,
    thread_id: str,  # noqa: ARG001 — schema is thread-independent
    page_type: Optional[str] = None,
) -> dict[str, Any]:
    selected = {page_type: FIELD_MAPPINGS[page_type]} if page_type and page_type in FIELD_MAPPINGS else FIELD_MAPPINGS

    pages: list[dict[str, Any]] = []
    for name, mapping in selected.items():
        pages.append(
            {
                "page_type": name,
                "page_title": name.replace("-", " ").title(),
                "fields": [
                    {
                        "field_id": fact_key,
                        "label": config["label"],
                        "selector": config["selector"],
                        "maps_to_tax_fact": fact_key,
                    }
                    for fact_key, config in mapping.items()
                ],
            }
        )
    return {"pages": pages, "count": sum(len(p["fields"]) for p in pages)}
