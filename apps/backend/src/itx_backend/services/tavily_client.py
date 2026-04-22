from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from itx_backend.config import settings

logger = logging.getLogger(__name__)


class TavilyUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TavilyHit:
    title: str
    url: str
    content: str
    score: float


class TavilySearchService:
    """Thin wrapper over Tavily's `/search` API.

    Tavily returns LLM-ready snippets with a score. Domain allowlisting lives here so every
    caller (including any future tool) benefits. If the API key is unset, `configured` is
    False and the tool returns a diagnostic rather than a crash.
    """

    def __init__(self) -> None:
        self._url = settings.tavily_base_url.rstrip("/")
        self._api_key = settings.tavily_api_key
        self._default_depth = settings.tavily_search_depth

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        *,
        query: str,
        include_domains: Optional[list[str]] = None,
        max_results: int = 5,
        search_depth: Optional[str] = None,
    ) -> list[TavilyHit]:
        if not query or not query.strip():
            return []
        if not self.configured:
            raise TavilyUnavailable("tavily_api_key_not_configured")

        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query.strip(),
            "max_results": max(1, min(max_results, 10)),
            "search_depth": search_depth or self._default_depth,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            payload["include_domains"] = include_domains

        try:
            data = await asyncio.to_thread(self._post, "/search", payload)
        except TavilyUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — normalise upstream failures
            raise TavilyUnavailable(f"tavily_request_failed:{type(exc).__name__}:{exc}") from exc

        hits: list[TavilyHit] = []
        for item in data.get("results", []) or []:
            if not isinstance(item, dict):
                continue
            hits.append(
                TavilyHit(
                    title=str(item.get("title") or ""),
                    url=str(item.get("url") or ""),
                    content=str(item.get("content") or "")[:1500],
                    score=float(item.get("score") or 0.0),
                )
            )
        return hits

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TavilyUnavailable(f"tavily_http_{exc.code}:{body[:240]}") from exc
        except urllib.error.URLError as exc:
            raise TavilyUnavailable(str(exc)) from exc


tavily_search = TavilySearchService()
