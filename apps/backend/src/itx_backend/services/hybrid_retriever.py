from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from itx_backend.config import settings
from itx_backend.db.session import get_pool
from itx_backend.services.cohere_client import cohere_rerank
from itx_backend.services.embedding_service import EmbeddingUnavailable, embedding_service
from itx_backend.services.qdrant_client import QdrantUnavailable, qdrant_store

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    """A single chunk surfaced by either retriever. Identity is the chunk primary key.

    The hybrid retriever collapses dense and BM25 hits onto this shape so RRF fusion and
    reranking operate over one canonical record per chunk. Source-specific raw scores are
    kept for debugging and for surfacing per-source rank in the response payload.
    """

    chunk_id: str
    document_id: str
    chunk_text: str
    file_name: str
    document_type: str
    page_number: Optional[int]
    section_name: Optional[str]
    # Raw per-source scores, kept purely for observability.
    dense_score: Optional[float] = None
    bm25_score: Optional[float] = None
    # Per-source ranks (1-based). None means "not returned by that source".
    dense_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    # Fusion outputs.
    rrf_score: float = 0.0
    rerank_score: Optional[float] = None
    source_tags: list[str] = field(default_factory=list)


def _rrf(rank: Optional[int], k: int) -> float:
    """Reciprocal Rank Fusion contribution for a single source.

    RRF combines ranked lists by summing `1 / (k + rank)`. The constant `k` (commonly 60)
    dampens the weight of the very top of each list so that a document appearing in the
    top-5 of both rankers beats a document that's #1 in only one. Returns 0 when the
    document did not appear in this source's top-N.
    """
    if rank is None or rank <= 0:
        return 0.0
    return 1.0 / (k + rank)


class HybridRetriever:
    """Dense + BM25 + RRF + Cohere rerank.

    Shape of the pipeline per query:
        1. Kick off dense (Qdrant) and BM25 (Postgres FTS) retrieval in parallel.
        2. Union candidates keyed by chunk_id (Postgres PK), carrying both rankings.
        3. Sum RRF contributions from each source into `rrf_score`.
        4. Take the top `fuse_top_k` by RRF and ask Cohere to rerank them.
        5. Return the top `final_top_k` by rerank score (or by RRF if rerank not configured).

    Failure policy: each stage degrades gracefully. If embeddings or Qdrant are down the
    retriever falls back to BM25-only. If BM25 fails it falls back to dense-only. If both
    fail it raises. Cohere rerank failures downgrade to RRF-only ranking.
    """

    async def retrieve(
        self,
        *,
        thread_id: str,
        query: str,
        top_k: Optional[int] = None,
        doc_types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        clean_query = (query or "").strip()
        if not clean_query:
            return {"query": query, "results": [], "mode": "empty_query", "stats": {}}

        dense_k = settings.retriever_dense_top_k
        bm25_k = settings.retriever_bm25_top_k
        fuse_k = settings.retriever_fuse_top_k
        final_k = max(1, min(top_k or settings.retriever_final_top_k, 10))

        dense_task = asyncio.create_task(
            self._dense_search(
                thread_id=thread_id, query=clean_query, top_k=dense_k, doc_types=doc_types
            )
        )
        bm25_task = asyncio.create_task(
            self._bm25_search(
                thread_id=thread_id, query=clean_query, top_k=bm25_k, doc_types=doc_types
            )
        )

        dense_hits, dense_error = await self._gather(dense_task)
        bm25_hits, bm25_error = await self._gather(bm25_task)

        if not dense_hits and not bm25_hits:
            reason = dense_error or bm25_error or "no_candidates"
            return {
                "query": clean_query,
                "results": [],
                "mode": "failed",
                "stats": {"reason": reason, "dense_error": dense_error, "bm25_error": bm25_error},
            }

        candidates = self._merge(dense_hits=dense_hits, bm25_hits=bm25_hits)

        # RRF fuse.
        rrf_k = settings.retriever_rrf_k
        for candidate in candidates.values():
            candidate.rrf_score = _rrf(candidate.dense_rank, rrf_k) + _rrf(candidate.bm25_rank, rrf_k)

        fused = sorted(candidates.values(), key=lambda c: c.rrf_score, reverse=True)[:fuse_k]

        # Optional rerank.
        rerank_mode = "skipped"
        if settings.retriever_rerank_enabled and cohere_rerank.configured and len(fused) > 1:
            hits = await cohere_rerank.rerank(
                query=clean_query,
                documents=[candidate.chunk_text for candidate in fused],
                top_n=len(fused),
            )
            if hits and any(hit.relevance_score > 0 for hit in hits):
                for hit in hits:
                    if 0 <= hit.index < len(fused):
                        fused[hit.index].rerank_score = hit.relevance_score
                fused.sort(key=lambda c: (c.rerank_score or -1.0), reverse=True)
                rerank_mode = "cohere"
            else:
                rerank_mode = "cohere_noop"
        elif not cohere_rerank.configured:
            rerank_mode = "not_configured"

        final = fused[:final_k]

        return {
            "query": clean_query,
            "results": [self._serialize(candidate) for candidate in final],
            "mode": self._mode_label(
                has_dense=bool(dense_hits), has_bm25=bool(bm25_hits), rerank=rerank_mode
            ),
            "stats": {
                "dense_count": len(dense_hits),
                "bm25_count": len(bm25_hits),
                "fused_count": len(fused),
                "final_count": len(final),
                "rerank": rerank_mode,
                "dense_error": dense_error,
                "bm25_error": bm25_error,
            },
        }

    async def _gather(self, task: asyncio.Task) -> tuple[list[Candidate], Optional[str]]:
        try:
            return (await task, None)
        except Exception as exc:  # noqa: BLE001 — per-source failure is caller-handled
            logger.warning("hybrid.source_failed", extra={"error": str(exc)})
            return ([], f"{type(exc).__name__}:{exc}")

    async def _dense_search(
        self,
        *,
        thread_id: str,
        query: str,
        top_k: int,
        doc_types: Optional[list[str]],
    ) -> list[Candidate]:
        try:
            vector = await embedding_service.embed_query(query)
        except EmbeddingUnavailable as exc:
            raise RuntimeError(f"embedding_unavailable:{exc}") from exc

        try:
            matches = await qdrant_store.search(
                vector=vector, thread_id=thread_id, top_k=top_k, doc_types=doc_types
            )
        except QdrantUnavailable as exc:
            raise RuntimeError(f"qdrant_unavailable:{exc}") from exc

        candidates: list[Candidate] = []
        for rank, match in enumerate(matches, start=1):
            payload = match.payload or {}
            chunk_id = self._chunk_identity(
                document_id=str(payload.get("document_id", "")),
                chunk_index=payload.get("chunk_index"),
                qdrant_id=match.id,
            )
            candidates.append(
                Candidate(
                    chunk_id=chunk_id,
                    document_id=str(payload.get("document_id", "")),
                    chunk_text=str(payload.get("chunk_text", "")),
                    file_name=str(payload.get("file_name", "Document")),
                    document_type=str(payload.get("doc_type", "unknown")),
                    page_number=payload.get("page_number"),
                    section_name=payload.get("section_name"),
                    dense_score=match.score,
                    dense_rank=rank,
                    source_tags=["dense"],
                )
            )
        return candidates

    async def _bm25_search(
        self,
        *,
        thread_id: str,
        query: str,
        top_k: int,
        doc_types: Optional[list[str]],
    ) -> list[Candidate]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                with q as (
                    select websearch_to_tsquery('english', $2::text) as tsq
                )
                select dc.id::text as chunk_id,
                       dc.document_id::text as document_id,
                       dc.chunk_text,
                       dc.page_number,
                       dc.section_name,
                       d.file_name,
                       d.doc_type,
                       ts_rank_cd(dc.fts, q.tsq) as bm25_score
                from document_chunks dc
                join documents d on d.id = dc.document_id
                cross join q
                where dc.thread_id = $1
                  and dc.fts @@ q.tsq
                  and ($3::text[] is null or d.doc_type = any($3::text[]))
                order by bm25_score desc
                limit $4
                """,
                thread_id,
                query,
                doc_types,
                max(1, min(top_k, 100)),
            )

        candidates: list[Candidate] = []
        for rank, row in enumerate(rows, start=1):
            candidates.append(
                Candidate(
                    chunk_id=str(row["chunk_id"]),
                    document_id=str(row["document_id"]),
                    chunk_text=str(row["chunk_text"] or ""),
                    file_name=str(row["file_name"] or "Document"),
                    document_type=str(row["doc_type"] or "unknown"),
                    page_number=row["page_number"],
                    section_name=row["section_name"],
                    bm25_score=float(row["bm25_score"] or 0),
                    bm25_rank=rank,
                    source_tags=["bm25"],
                )
            )
        return candidates

    def _merge(
        self,
        *,
        dense_hits: list[Candidate],
        bm25_hits: list[Candidate],
    ) -> dict[str, Candidate]:
        """Merge two source lists keyed by chunk identity.

        Dense candidates come from Qdrant where the point id is `uuid5(document_id, chunk_index)`.
        BM25 candidates come from the Postgres chunk primary key. We canonicalise to
        `(document_id, chunk_index)` when we can read it off the dense payload, and fall back to
        the Qdrant point id so the two never accidentally merge across different chunks. Chunks
        that overlap in both sources will therefore only merge if we can recover chunk_index from
        the dense payload — accept that small duplication cost in exchange for correctness.
        """
        merged: dict[str, Candidate] = {}
        # Start with BM25 — its chunk_id is authoritative (Postgres PK).
        for candidate in bm25_hits:
            merged[candidate.chunk_id] = candidate

        for candidate in dense_hits:
            # Try to find the BM25 twin by document_id + chunk_text match; cheap because
            # hit counts are small (top_k ~= 30). This also handles the case where a chunk
            # was reindexed and Qdrant/Postgres ids no longer line up.
            twin = self._find_twin(candidate, merged)
            if twin is not None:
                twin.dense_score = candidate.dense_score
                twin.dense_rank = candidate.dense_rank
                if "dense" not in twin.source_tags:
                    twin.source_tags.append("dense")
            else:
                merged[candidate.chunk_id] = candidate

        return merged

    def _find_twin(
        self, candidate: Candidate, pool: dict[str, Candidate]
    ) -> Optional[Candidate]:
        for other in pool.values():
            if other.document_id != candidate.document_id:
                continue
            if other.chunk_text and candidate.chunk_text and other.chunk_text == candidate.chunk_text:
                return other
        return None

    def _chunk_identity(
        self,
        *,
        document_id: str,
        chunk_index: Any,
        qdrant_id: str,
    ) -> str:
        if document_id and chunk_index is not None:
            return f"{document_id}:{int(chunk_index)}"
        return f"qdrant:{qdrant_id}"

    def _serialize(self, candidate: Candidate) -> dict[str, Any]:
        return {
            "document_id": candidate.document_id,
            "file_name": candidate.file_name,
            "document_type": candidate.document_type,
            "page_number": candidate.page_number,
            "section_name": candidate.section_name,
            "chunk_text": candidate.chunk_text,
            "sources": candidate.source_tags,
            "scores": {
                "dense": candidate.dense_score,
                "bm25": candidate.bm25_score,
                "rrf": round(candidate.rrf_score, 6),
                "rerank": candidate.rerank_score,
            },
            "ranks": {
                "dense": candidate.dense_rank,
                "bm25": candidate.bm25_rank,
            },
            "citation": self._citation(candidate),
        }

    def _citation(self, candidate: Candidate) -> str:
        label = candidate.file_name or "Document"
        if candidate.page_number is not None:
            return f"{label}:p.{candidate.page_number}"
        if candidate.section_name:
            return f"{label}#{candidate.section_name}"
        return label

    def _mode_label(self, *, has_dense: bool, has_bm25: bool, rerank: str) -> str:
        if has_dense and has_bm25:
            base = "hybrid_rrf"
        elif has_dense:
            base = "dense_only"
        elif has_bm25:
            base = "bm25_only"
        else:
            base = "empty"
        return f"{base}+{rerank}" if rerank not in {"skipped", "not_configured"} else base


hybrid_retriever = HybridRetriever()
