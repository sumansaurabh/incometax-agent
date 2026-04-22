from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).parent.parent / "knowledge_base"
_TOPIC_FILES = {
    "definitions": "definitions.json",
    "regimes": "regimes.json",
    "sections": "sections.json",
    "forms": "forms.json",
    "slabs": "slabs.json",
}

_WORD_RE = re.compile(r"[a-z0-9]+")


class _KnowledgeBase:
    """In-process curated rule pack. Loaded once from JSON on first use.

    Matching is intentionally simple: a token/alias overlap score. The KB is small (a few dozen
    entries) so anything fancier than a linear scan is wasted complexity. Each entry carries
    `aliases` specifically so that short user queries like 'AIS' or '87A' score a direct alias
    hit and don't have to rely on the body text.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._by_topic: dict[str, list[dict[str, Any]]] = {}

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        for topic, filename in _TOPIC_FILES.items():
            path = _KB_DIR / filename
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                logger.warning("kb.missing_file", extra={"topic": topic, "path": str(path)})
                self._by_topic[topic] = []
                continue
            except json.JSONDecodeError as exc:
                logger.error("kb.invalid_json", extra={"topic": topic, "path": str(path), "error": str(exc)})
                self._by_topic[topic] = []
                continue
            entries = data.get("entries") if isinstance(data, dict) else None
            if not isinstance(entries, list):
                self._by_topic[topic] = []
                continue
            self._by_topic[topic] = [e for e in entries if isinstance(e, dict)]
        self._loaded = True

    def search(
        self,
        *,
        query: str,
        topic: Optional[str] = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        query_tokens = set(_WORD_RE.findall(query.lower())) if query else set()
        query_raw = query.lower().strip() if query else ""

        topics = [topic] if topic and topic in self._by_topic else list(self._by_topic.keys())
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for t in topics:
            for entry in self._by_topic.get(t, []):
                score = self._score(entry=entry, query_tokens=query_tokens, query_raw=query_raw)
                if score > 0:
                    scored.append((score, t, entry))

        scored.sort(key=lambda triple: triple[0], reverse=True)
        top = scored[: max(1, min(top_k, 10))]
        return [
            {
                "topic": matched_topic,
                "id": entry.get("id"),
                "title": entry.get("title"),
                "body": entry.get("body"),
                "aliases": entry.get("aliases", []),
                "score": round(score, 3),
            }
            for score, matched_topic, entry in top
        ]

    def _score(
        self,
        *,
        entry: dict[str, Any],
        query_tokens: set[str],
        query_raw: str,
    ) -> float:
        if not query_raw:
            return 0.0

        aliases = [str(a).lower() for a in entry.get("aliases", []) if a]
        title = str(entry.get("title", "")).lower()
        body = str(entry.get("body", "")).lower()

        # Alias matches are the strongest signal. We accumulate all matching aliases rather than
        # returning on the first hit so longer queries (e.g. "updated return 139(8A)") don't
        # prematurely score lower than entries that merely share a section number.
        alias_bonus = 0.0
        for alias in aliases:
            if alias == query_raw:
                alias_bonus = max(alias_bonus, 10.0)
            elif alias and alias in query_raw:
                # Longer alias substrings are more specific — weight by length so "updated return"
                # outscores a bare "139" match.
                weight = 6.0 + min(len(alias), 30) * 0.1
                alias_bonus = max(alias_bonus, weight)

        if not query_tokens and alias_bonus == 0.0:
            return 0.0

        alias_tokens: set[str] = set()
        for alias in aliases:
            alias_tokens.update(_WORD_RE.findall(alias))
        title_tokens = set(_WORD_RE.findall(title))
        body_tokens = set(_WORD_RE.findall(body))

        alias_overlap = len(query_tokens & alias_tokens)
        title_overlap = len(query_tokens & title_tokens)
        body_overlap = len(query_tokens & body_tokens)

        token_score = alias_overlap * 3.0 + title_overlap * 2.0 + body_overlap * 0.5
        # An exact-alias hit trumps token scoring; otherwise combine.
        if alias_bonus >= 10.0:
            return alias_bonus
        return alias_bonus + token_score

    def topics(self) -> list[str]:
        self._ensure_loaded()
        return list(self._by_topic.keys())


_kb = _KnowledgeBase()


@tool_registry.tool(
    name="kb_lookup",
    description=(
        "Look up curated Indian income-tax knowledge: definitions (AIS, TIS, Form 16, Form 26AS, "
        "HRA, standard deduction, 44AB, 87A), regime slabs (old and new, AY 2025-26), sections "
        "of the Income Tax Act (80C, 80D, 80CCD(1B), 80CCD(2), 80G, 80TTA, 139(1)/(4)/(5)/(8A), "
        "234F), ITR forms (ITR-1/2/3/4/U), slabs and surcharge and capital-gains rates. Prefer "
        "this tool over general knowledge for any factual tax question — the entries are curated "
        "and cite specific amounts and AYs. Pass a concise `query` (e.g. 'AIS', 'new regime "
        "slabs', '80C limit', 'belated return deadline'). Optionally narrow by `topic`. Returns "
        "up to 3 matching entries with title, body, and aliases."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Short search query; usually 1-5 words. Use the term the user asked about.",
            },
            "topic": {
                "type": "string",
                "enum": ["definitions", "regimes", "sections", "forms", "slabs"],
                "description": "Optional topic to restrict the search. Omit to search all topics.",
            },
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "default": 3,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
async def kb_lookup(
    *,
    thread_id: str,  # noqa: ARG001 — required by the runner contract; KB lookup is thread-independent
    query: str,
    topic: Optional[str] = None,
    top_k: int = 3,
) -> dict[str, Any]:
    if not query or not query.strip():
        return {"matches": [], "error": "query_required"}
    results = _kb.search(query=query, topic=topic, top_k=top_k)
    return {
        "query": query,
        "topic": topic,
        "matches": results,
        "topics_available": _kb.topics(),
    }
