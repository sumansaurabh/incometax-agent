from __future__ import annotations

import logging
from typing import Any, Optional

from itx_backend.agent.tool_registry import tool_registry
from itx_backend.services.tavily_client import TavilyUnavailable, tavily_search

logger = logging.getLogger(__name__)


# Allowlist of trustworthy sources for Indian income tax questions. Ordered roughly by
# authority — official government first, then well-known compliance publishers. The tool
# enforces this list; the model cannot override it via the tool call.
_ALLOWED_DOMAINS = [
    "incometax.gov.in",
    "eportal.incometax.gov.in",
    "tin-nsdl.com",
    "tin.tin.nsdl.com",
    "cbdt.gov.in",
    "cbic.gov.in",
    "finmin.nic.in",
    "indiankanoon.org",
    "cleartax.in",
    "taxguru.in",
    "economictimes.indiatimes.com",
]


_TOPIC_DOMAIN_HINTS: dict[str, list[str]] = {
    "portal": ["eportal.incometax.gov.in", "incometax.gov.in"],
    "law": ["incometax.gov.in", "indiankanoon.org", "cbdt.gov.in"],
    "tds": ["tin-nsdl.com", "incometax.gov.in"],
    "news": ["economictimes.indiatimes.com", "incometax.gov.in"],
    "howto": ["incometax.gov.in", "cleartax.in", "taxguru.in"],
}


@tool_registry.tool(
    name="web_search",
    description=(
        "Search authoritative Indian tax sources on the live web. The tool is allowlisted to "
        "official sites (incometax.gov.in, tin-nsdl.com, cbdt.gov.in) and established tax "
        "publishers (cleartax, taxguru, economictimes). Use it when the user asks about: recent "
        "circulars/notifications, a specific section of the Income Tax Act, current portal "
        "behaviour not captured in your knowledge base, news about filing deadlines, or a "
        "numerical limit that may have changed. Always cite the url returned, and prefer "
        "government domains over publishers. DO NOT use this for facts about the user's own "
        "documents — use document_search for that. Results are typically 3-5 snippets with "
        "title, url, content excerpt, and a relevance score."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused natural-language query. Include the section number or named concept if known.",
            },
            "topic": {
                "type": "string",
                "enum": ["portal", "law", "tds", "news", "howto"],
                "description": (
                    "Optional: biases the domain allowlist. 'portal' favours the e-filing portal, "
                    "'law' favours CBDT and indiankanoon, 'tds' favours tin-nsdl, 'news' favours "
                    "ET, 'howto' favours cleartax/taxguru. Omit to search all allowlisted domains."
                ),
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
async def web_search(
    *,
    thread_id: str,  # noqa: ARG001 — web search is thread-independent
    query: str,
    topic: Optional[str] = None,
    max_results: int = 5,
) -> dict[str, Any]:
    if not query or not query.strip():
        return {"error": "query_required"}

    domains = list(_ALLOWED_DOMAINS)
    if topic and topic in _TOPIC_DOMAIN_HINTS:
        # Keep the allowlist effect but push preferred domains to the front — Tavily
        # respects include_domains as a strict filter, so this stays safe either way.
        preferred = _TOPIC_DOMAIN_HINTS[topic]
        domains = preferred + [d for d in _ALLOWED_DOMAINS if d not in preferred]

    try:
        hits = await tavily_search.search(
            query=query,
            include_domains=domains,
            max_results=max_results,
        )
    except TavilyUnavailable as exc:
        return {
            "error": str(exc),
            "hint": (
                "Web search is temporarily unavailable or not configured. Ask the user to try "
                "again later, or answer from kb_lookup / document_search if possible."
            ),
            "results": [],
        }

    return {
        "query": query,
        "topic": topic,
        "domains_searched": domains,
        "results": [
            {
                "title": hit.title,
                "url": hit.url,
                "content": hit.content,
                "score": round(hit.score, 4),
            }
            for hit in hits
        ],
    }
