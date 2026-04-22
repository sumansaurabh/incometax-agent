from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry

logger = logging.getLogger(__name__)


_KB_PATH = Path(__file__).parent.parent / "knowledge_base" / "portal_how_to.json"
_WORD_RE = re.compile(r"[a-z0-9]+")


class _HowToIndex:
    """Lazy-loaded index of curated how-to recipes."""

    def __init__(self) -> None:
        self._entries: Optional[list[dict[str, Any]]] = None

    def _ensure_loaded(self) -> list[dict[str, Any]]:
        if self._entries is not None:
            return self._entries
        try:
            data = json.loads(_KB_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("how_to.load_failed", extra={"error": str(exc)})
            self._entries = []
            return self._entries
        entries = data.get("entries", [])
        self._entries = [entry for entry in entries if isinstance(entry, dict)]
        return self._entries

    def ids(self) -> list[str]:
        return [entry.get("id", "") for entry in self._ensure_loaded()]

    def by_id(self, recipe_id: str) -> Optional[dict[str, Any]]:
        for entry in self._ensure_loaded():
            if entry.get("id") == recipe_id:
                return entry
        return None

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        entries = self._ensure_loaded()
        query_norm = query.lower().strip()
        query_tokens = set(_WORD_RE.findall(query_norm))

        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in entries:
            aliases = [str(alias).lower() for alias in entry.get("aliases", []) if alias]
            title = str(entry.get("title", "")).lower()
            score = 0.0

            # Exact or substring alias match — the authoritative signal for how-to queries.
            if any(alias == query_norm for alias in aliases):
                score = 100.0
            elif any(alias in query_norm or query_norm in alias for alias in aliases if alias):
                score = 50.0
            else:
                alias_tokens: set[str] = set()
                for alias in aliases:
                    alias_tokens.update(_WORD_RE.findall(alias))
                title_tokens = set(_WORD_RE.findall(title))
                score = 3.0 * len(query_tokens & alias_tokens) + 2.0 * len(query_tokens & title_tokens)

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _score, entry in scored[: max(1, min(top_k, 5))]]


_index = _HowToIndex()


@tool_registry.tool(
    name="how_to",
    description=(
        "Return step-by-step instructions for a named e-Filing portal task: filing an ITR, "
        "checking refund status, e-verifying, downloading Form 26AS / AIS, pre-validating a bank "
        "account, filing a revised/belated/updated return, paying self-assessment tax via "
        "Challan 280, linking Aadhaar, rectification under 154, downloading ITR-V, raising a "
        "grievance, and more. Prefer this tool over web_search for procedural 'how do I...' "
        "questions — the recipes are curated with direct portal URLs. Supply either `query` (free "
        "text like 'how do I file revised return?') or `recipe_id` (exact key like "
        "'revised_return'). Available recipe ids: " + ", ".join(_index.ids() or ["<loading>"]) + "."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language user question, e.g. 'how do I e-verify my return?'",
            },
            "recipe_id": {
                "type": "string",
                "description": "Exact recipe id. Use when you already know the precise entry.",
            },
        },
        "additionalProperties": False,
    },
)
async def how_to(
    *,
    thread_id: str,  # noqa: ARG001 — how-to content is thread-independent
    query: Optional[str] = None,
    recipe_id: Optional[str] = None,
) -> dict[str, Any]:
    if not query and not recipe_id:
        return {"error": "query_or_recipe_id_required"}

    if recipe_id:
        entry = _index.by_id(recipe_id)
        if entry is None:
            return {
                "error": "recipe_not_found",
                "recipe_id": recipe_id,
                "available": _index.ids(),
            }
        return {"match": "exact", "recipe": entry}

    matches = _index.search(query or "", top_k=3)
    if not matches:
        return {
            "match": "none",
            "query": query,
            "available": _index.ids(),
            "hint": "No recipe matched. Try web_search for an authoritative external answer.",
        }
    return {
        "match": "search",
        "query": query,
        "recipes": matches,
    }
