from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from itx_backend.services.embedding_service import EmbeddingUnavailable, embedding_service
from itx_backend.services.qdrant_client import QdrantUnavailable, qdrant_store
from itx_workers.pipelines.chunking import chunk_processed_document


async def index_document_embeddings(processed: dict[str, Any]) -> dict[str, Any]:
    thread_id = processed.get("thread_id")
    document_id = processed.get("document_id")
    if not thread_id or not document_id:
        return {"status": "skipped", "reason": "thread_id_or_document_id_missing", "chunk_count": 0}

    chunks = chunk_processed_document(processed)
    if not chunks:
        return {"status": "skipped", "reason": "no_text_chunks", "chunk_count": 0}

    texts = [str(chunk["chunk_text"]) for chunk in chunks]
    try:
        vectors = await embedding_service.embed_texts(texts)
        await qdrant_store.delete_document(str(document_id))
        created_at = datetime.now(timezone.utc).isoformat()
        points = []
        for chunk, vector in zip(chunks, vectors):
            chunk_index = int(chunk["chunk_index"])
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"itx:{document_id}:{chunk_index}"))
            points.append(
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "thread_id": str(thread_id),
                        "document_id": str(document_id),
                        "doc_type": str(processed.get("document_type") or processed.get("doc_type") or "unknown"),
                        "chunk_index": chunk_index,
                        "chunk_text": str(chunk["chunk_text"]),
                        "page_number": chunk.get("page_number"),
                        "section_name": chunk.get("section_name"),
                        "file_name": str(processed.get("file_name") or processed.get("name") or "Document"),
                        "created_at": created_at,
                    },
                }
            )
        await qdrant_store.upsert(points)
    except EmbeddingUnavailable as exc:
        return {"status": "skipped", "reason": str(exc), "chunk_count": len(chunks)}
    except QdrantUnavailable as exc:
        return {"status": "failed", "reason": str(exc), "chunk_count": len(chunks)}

    return {
        "status": "indexed",
        "chunk_count": len(chunks),
        "model": embedding_service.model,
        "dimensions": embedding_service.dimensions,
    }
