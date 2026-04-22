from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from itx_backend.config import settings


class QdrantUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VectorSearchResult:
    id: str
    score: float
    payload: dict[str, Any]


class QdrantVectorStore:
    def __init__(self) -> None:
        self.url = settings.qdrant_url.rstrip("/")
        self.collection = settings.qdrant_collection
        self.dimensions = settings.embedding_dimensions

    async def ensure_collection(self) -> None:
        exists = await self._request("GET", f"/collections/{self.collection}", allow_not_found=True)
        if exists is not None:
            return
        await self._request(
            "PUT",
            f"/collections/{self.collection}",
            {
                "vectors": {
                    "size": self.dimensions,
                    "distance": "Cosine",
                }
            },
        )

    async def upsert(self, points: list[dict[str, Any]]) -> None:
        if not points:
            return
        await self.ensure_collection()
        await self._request("PUT", f"/collections/{self.collection}/points?wait=true", {"points": points})

    async def delete_document(self, document_id: str) -> None:
        await self.ensure_collection()
        await self._request(
            "POST",
            f"/collections/{self.collection}/points/delete?wait=true",
            {"filter": {"must": [{"key": "document_id", "match": {"value": document_id}}]}},
        )

    async def search(
        self,
        *,
        vector: list[float],
        thread_id: str,
        top_k: int,
        doc_types: Optional[list[str]] = None,
    ) -> list[VectorSearchResult]:
        await self.ensure_collection()
        filters: list[dict[str, Any]] = [{"key": "thread_id", "match": {"value": thread_id}}]
        if doc_types:
            filters.append({"key": "doc_type", "match": {"any": doc_types}})
        payload = await self._request(
            "POST",
            f"/collections/{self.collection}/points/search",
            {
                "vector": vector,
                "limit": max(1, min(top_k, 20)),
                "with_payload": True,
                "filter": {"must": filters},
            },
        )
        return [
            VectorSearchResult(
                id=str(item.get("id")),
                score=float(item.get("score", 0)),
                payload=dict(item.get("payload") or {}),
            )
            for item in payload.get("result", [])
        ]

    async def stats(self) -> dict[str, Any]:
        health = await self._request("GET", "/healthz", allow_not_found=True)
        collection = await self._request("GET", f"/collections/{self.collection}", allow_not_found=True)
        return {
            "url": self.url,
            "collection_name": self.collection,
            "healthy": health is not None,
            "collection_exists": collection is not None,
            "collection": collection.get("result", {}) if collection else None,
        }

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        *,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._request_sync, method, path, payload, allow_not_found)

    def _request_sync(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]],
        allow_not_found: bool,
    ) -> dict[str, Any] | None:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"raw": raw}
        except urllib.error.HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            body = exc.read().decode("utf-8", errors="replace")
            raise QdrantUnavailable(f"qdrant_request_failed:{exc.code}:{body[:240]}") from exc
        except urllib.error.URLError as exc:
            if allow_not_found:
                return None
            raise QdrantUnavailable(str(exc)) from exc


qdrant_store = QdrantVectorStore()
