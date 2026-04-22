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


class CohereUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RerankHit:
    index: int
    relevance_score: float


class CohereRerankService:
    """Thin wrapper over Cohere's `/rerank` endpoint.

    The hybrid retriever calls this with the fused top-N candidates to get a
    cross-encoder style reranking. Falls back to the identity ranking if the
    API is not configured or a call fails transiently — retrieval quality
    should degrade gracefully, not break chat.
    """

    def __init__(self) -> None:
        self._url = settings.cohere_base_url.rstrip("/")
        self._api_key = settings.cohere_api_key
        self._model = settings.cohere_rerank_model

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: Optional[int] = None,
    ) -> list[RerankHit]:
        if not documents:
            return []
        if not self.configured:
            return [RerankHit(index=i, relevance_score=0.0) for i in range(len(documents))]

        limit = top_n if top_n is not None else len(documents)
        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": max(1, min(limit, len(documents))),
        }

        try:
            result = await asyncio.to_thread(self._post, "/rerank", payload)
        except CohereUnavailable as exc:
            logger.warning("cohere.rerank_failed", extra={"error": str(exc)})
            return [RerankHit(index=i, relevance_score=0.0) for i in range(len(documents))]

        hits: list[RerankHit] = []
        for item in result.get("results", []):
            idx = item.get("index")
            score = item.get("relevance_score")
            if isinstance(idx, int) and isinstance(score, (int, float)):
                hits.append(RerankHit(index=idx, relevance_score=float(score)))
        return hits

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise CohereUnavailable(f"cohere_http_{exc.code}:{body[:240]}") from exc
        except urllib.error.URLError as exc:
            raise CohereUnavailable(str(exc)) from exc


cohere_rerank = CohereRerankService()
