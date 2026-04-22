from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from itx_backend.config import settings


class EmbeddingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingStatus:
    configured: bool
    model: str
    dimensions: int
    detail: str


class OpenAIEmbeddingService:
    def __init__(self) -> None:
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self.batch_size = max(1, min(settings.embedding_batch_size, 2048))
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key

    def status(self) -> EmbeddingStatus:
        if not self.api_key:
            return EmbeddingStatus(
                configured=False,
                model=self.model,
                dimensions=self.dimensions,
                detail="ITX_OPENAI_API_KEY is not configured",
            )
        return EmbeddingStatus(
            configured=True,
            model=self.model,
            dimensions=self.dimensions,
            detail="configured",
        )

    async def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        clean_texts = [text.strip() for text in texts if text and text.strip()]
        if not clean_texts:
            return []
        if not self.api_key:
            raise EmbeddingUnavailable("openai_api_key_not_configured")

        vectors: list[list[float]] = []
        for start in range(0, len(clean_texts), self.batch_size):
            batch = clean_texts[start : start + self.batch_size]
            vectors.extend(await self._embed_batch(batch))
        return vectors

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        if not vectors:
            raise EmbeddingUnavailable("empty_query")
        return vectors[0]

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await asyncio.to_thread(self._request_embeddings, texts)
            except (urllib.error.URLError, TimeoutError, EmbeddingUnavailable) as exc:
                last_error = exc
                await asyncio.sleep(0.3 * (attempt + 1))
        raise EmbeddingUnavailable(str(last_error or "embedding_request_failed"))

    def _request_embeddings(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": texts,
        }
        if self.dimensions > 0:
            payload["dimensions"] = self.dimensions

        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise EmbeddingUnavailable(f"openai_embedding_failed:{exc.code}:{body[:240]}") from exc

        vectors = [item["embedding"] for item in sorted(data.get("data", []), key=lambda item: item.get("index", 0))]
        if len(vectors) != len(texts):
            raise EmbeddingUnavailable(f"embedding_count_mismatch:{len(vectors)}:{len(texts)}")
        if time.monotonic() - started > 25:
            raise EmbeddingUnavailable("embedding_request_timed_out")
        return vectors


embedding_service = OpenAIEmbeddingService()
