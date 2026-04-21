from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Optional

from asyncpg import Record

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.nodes import document_intake, extract_facts
from itx_backend.db.session import get_pool
from itx_workers.document_pipeline import process_document


PIPELINE_VERSION = "phase2-doc-intel-1"


class DocumentService:
    async def create_upload(
        self,
        *,
        file_name: str,
        mime_type: str,
        thread_id: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> dict[str, Any]:
        document_id = uuid.uuid4()
        storage_uri = f"documents/{document_id}/{file_name}"
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into documents (
                    id, thread_id, file_name, storage_uri, mime, doc_type,
                    classification_confidence, status
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                document_id,
                thread_id,
                file_name,
                storage_uri,
                mime_type,
                doc_type or "unknown",
                0,
                "pending_upload",
            )
            await connection.execute(
                """
                insert into document_versions (id, document_id, version_no, storage_uri)
                values ($1, $2, $3, $4)
                """,
                uuid.uuid4(),
                document_id,
                1,
                storage_uri,
            )

        return {
            "document_id": str(document_id),
            "thread_id": thread_id,
            "status": "pending_upload",
            "storage_uri": storage_uri,
            "upload_url": f"/api/documents/{document_id}/ingest",
        }

    async def ingest_document(
        self,
        *,
        document_id: str,
        raw_text: str,
        thread_id: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> dict[str, Any]:
        if not raw_text.strip():
            raise ValueError("raw_text is required")

        parsed_document_id = uuid.UUID(document_id)
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, file_name, storage_uri, mime, doc_type
                from documents
                where id = $1
                """,
                parsed_document_id,
            )

        if row is None:
            raise KeyError(document_id)

        effective_thread_id = thread_id or row["thread_id"]
        payload = {
            "document_id": str(row["id"]),
            "thread_id": effective_thread_id,
            "file_name": row["file_name"],
            "mime_type": row["mime"],
            "doc_type": doc_type or row["doc_type"],
            "storage_uri": row["storage_uri"],
            "raw_text": raw_text,
        }
        processed = await process_document(payload)
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        entities = processed.get("entities", [])
        normalized_fields = processed.get("normalized_fields", {})
        extraction_confidence = float(
            processed.get("parsed", {}).get("confidence")
            or processed.get("classification_confidence")
            or 0
        )

        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "delete from document_entities where document_id = $1",
                    parsed_document_id,
                )
                await connection.execute(
                    """
                    update documents
                    set thread_id = $2,
                        sha256 = $3,
                        byte_size = $4,
                        doc_type = $5,
                        classification_confidence = $6,
                        status = $7,
                        parsed_at = now(),
                        updated_at = now()
                    where id = $1
                    """,
                    parsed_document_id,
                    effective_thread_id,
                    sha256,
                    len(raw_text.encode("utf-8")),
                    processed.get("document_type", doc_type or row["doc_type"] or "unknown"),
                    processed.get("classification_confidence", 0),
                    "parsed",
                )
                await connection.execute(
                    """
                    insert into document_extractions (
                        id, document_id, extractor_name, extractor_version,
                        raw_json, normalized_json, confidence
                    )
                    values ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
                    """,
                    uuid.uuid4(),
                    parsed_document_id,
                    processed.get("parsed", {}).get("parser", "unknown"),
                    PIPELINE_VERSION,
                    json.dumps(
                        {
                            "classification_confidence": processed.get("classification_confidence"),
                            "parser_output": processed.get("parsed", {}),
                            "warnings": processed.get("parsed", {}).get("warnings", []),
                            "tables": processed.get("tables", []),
                        },
                        sort_keys=True,
                    ),
                    json.dumps(normalized_fields, sort_keys=True),
                    extraction_confidence,
                )

                for entity in entities:
                    entity_value = entity.get("value")
                    if isinstance(entity_value, (dict, list)):
                        entity_value = json.dumps(entity_value, sort_keys=True)
                    await connection.execute(
                        """
                        insert into document_entities (
                            id, document_id, page_no, entity_type, value, normalized, confidence
                        )
                        values ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        uuid.uuid4(),
                        parsed_document_id,
                        entity.get("page", 1),
                        entity.get("type", "unknown"),
                        str(entity_value),
                        entity.get("normalized") and str(entity.get("normalized")),
                        float(entity.get("confidence", 0) or 0),
                    )

        processed_document = {
            "id": str(row["id"]),
            "name": row["file_name"],
            "type": processed.get("document_type", "unknown"),
            "mime_type": row["mime"],
            "storage_uri": row["storage_uri"],
            "sanitized": True,
            "virus_scan": "clean",
            "parser": processed.get("parsed", {}).get("parser", "unknown"),
            "parser_confidence": extraction_confidence,
            "classification_confidence": processed.get("classification_confidence", 0),
            "normalized_fields": normalized_fields,
            "entities": entities,
            "extraction_warnings": processed.get("parsed", {}).get("warnings", []),
            "sha256": sha256,
        }

        attached_summary = None
        if effective_thread_id:
            attached_summary = await self._attach_to_thread(effective_thread_id, processed_document)

        return {
            "document_id": str(row["id"]),
            "thread_id": effective_thread_id,
            "status": "parsed",
            "document_type": processed_document["type"],
            "parser": processed_document["parser"],
            "classification_confidence": processed_document["classification_confidence"],
            "normalized_fields": normalized_fields,
            "entities": entities,
            "warnings": processed_document["extraction_warnings"],
            "attached_thread": attached_summary,
        }

    async def list_documents(self, thread_id: str) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select d.id,
                       d.thread_id,
                       d.file_name,
                       d.mime,
                       d.doc_type,
                       d.status,
                       d.storage_uri,
                       d.uploaded_at,
                       d.parsed_at,
                       d.classification_confidence,
                       de.normalized_json::text as normalized_json
                from documents d
                left join lateral (
                    select normalized_json
                    from document_extractions
                    where document_id = d.id
                    order by created_at desc
                    limit 1
                ) de on true
                where d.thread_id = $1
                order by d.uploaded_at desc
                """,
                thread_id,
            )
        return [self._serialize_document_row(row) for row in rows]

    async def _attach_to_thread(self, thread_id: str, processed_document: dict[str, Any]) -> Optional[dict[str, Any]]:
        state = await checkpointer.latest(thread_id)
        if state is None:
            return None

        documents = [doc for doc in state.documents if doc.get("id") != processed_document["id"]]
        documents.append(processed_document)
        state.documents = documents
        state = await document_intake.run(state)
        state = await extract_facts.run(state)
        await checkpointer.save(state)
        return {
            "thread_id": thread_id,
            "document_count": len(state.documents),
            "tax_facts": state.tax_facts,
        }

    def _serialize_document_row(self, row: Record) -> dict[str, Any]:
        normalized_text = row["normalized_json"]
        return {
            "document_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "file_name": row["file_name"],
            "mime_type": row["mime"],
            "document_type": row["doc_type"],
            "status": row["status"],
            "storage_uri": row["storage_uri"],
            "classification_confidence": float(row["classification_confidence"] or 0),
            "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
            "parsed_at": row["parsed_at"].isoformat() if row["parsed_at"] else None,
            "normalized_fields": json.loads(normalized_text) if normalized_text else {},
        }


document_service = DocumentService()