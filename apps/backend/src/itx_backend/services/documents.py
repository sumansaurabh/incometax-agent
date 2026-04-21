from __future__ import annotations

import base64
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Optional

from asyncpg import Record

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.nodes import document_intake, extract_facts, infer_itr, reconcile
from itx_backend.config import settings
from itx_backend.db.session import get_pool
from itx_backend.services.document_storage import document_storage
from itx_workers.parsers.common import decode_text_bytes
from itx_workers.document_pipeline import process_document
from itx_workers.queue import QueueJob, drain, enqueue
from itx_workers.security.sanitize import sanitize_text
from itx_workers.security.virus_scan import scan as virus_scan


PIPELINE_VERSION = "phase2-doc-intel-1"


class DocumentService:
    async def create_upload(
        self,
        *,
        file_name: str,
        mime_type: str,
        thread_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        document_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        pool = await get_pool()
        safe_file_name = Path(file_name).name
        document_uuid: uuid.UUID
        version_no: int
        storage_uri: str

        if document_id is None:
            document_uuid = uuid.uuid4()
            version_no = 1
            storage_uri = f"documents/{document_uuid}/v{version_no}/{safe_file_name}"
        else:
            document_uuid = uuid.UUID(document_id)
            async with pool.acquire() as connection:
                existing = await connection.fetchrow(
                    "select file_name, mime, doc_type, thread_id from documents where id = $1",
                    document_uuid,
                )
                if existing is None:
                    raise KeyError(document_id)
                version_no = int(
                    await connection.fetchval(
                        "select coalesce(max(version_no), 0) + 1 from document_versions where document_id = $1",
                        document_uuid,
                    )
                )
                thread_id = thread_id or existing["thread_id"]
                mime_type = mime_type or existing["mime"]
                doc_type = doc_type or existing["doc_type"]
                if not safe_file_name:
                    safe_file_name = existing["file_name"]
            storage_uri = f"documents/{document_uuid}/v{version_no}/{safe_file_name}"

        signed = document_storage.create_signed_upload(str(document_uuid), version_no, storage_uri)
        pool = await get_pool()
        async with pool.acquire() as connection:
            if document_id is None:
                await connection.execute(
                    """
                    insert into documents (
                        id, thread_id, file_name, storage_uri, mime, doc_type,
                        classification_confidence, status
                    )
                    values ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    document_uuid,
                    thread_id,
                    safe_file_name,
                    storage_uri,
                    mime_type,
                    doc_type or "unknown",
                    0,
                    "pending_upload",
                )
            else:
                await connection.execute(
                    """
                    update documents
                    set thread_id = $2,
                        file_name = $3,
                        storage_uri = $4,
                        mime = $5,
                        doc_type = $6,
                        status = $7,
                        updated_at = now()
                    where id = $1
                    """,
                    document_uuid,
                    thread_id,
                    safe_file_name,
                    storage_uri,
                    mime_type,
                    doc_type or "unknown",
                    "pending_upload",
                )
            await connection.execute(
                """
                insert into document_versions (id, document_id, version_no, storage_uri, reason)
                values ($1, $2, $3, $4, $5)
                """,
                uuid.uuid4(),
                document_uuid,
                version_no,
                storage_uri,
                reason,
            )

        return {
            "document_id": str(document_uuid),
            "thread_id": thread_id,
            "status": "pending_upload",
            "storage_uri": storage_uri,
            "version_no": version_no,
            "upload_url": (
                f"/api/documents/{document_uuid}/content"
                f"?version_no={version_no}&expires={signed['expires']}&signature={signed['signature']}"
            ),
            "expires": signed["expires"],
            "signature": signed["signature"],
        }

    async def upload_document_content(
        self,
        *,
        document_id: str,
        version_no: int,
        expires: int,
        signature: str,
        content_bytes: bytes,
        thread_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        process_immediately: bool = True,
    ) -> dict[str, Any]:
        parsed_document_id = uuid.UUID(document_id)
        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select d.id, d.thread_id, d.file_name, d.storage_uri, d.mime, d.doc_type,
                       dv.storage_uri as version_storage_uri
                from documents d
                join document_versions dv on dv.document_id = d.id and dv.version_no = $2
                where d.id = $1
                """,
                parsed_document_id,
                version_no,
            )

        if row is None:
            raise KeyError(document_id)

        storage_uri = row["version_storage_uri"]
        if not document_storage.verify_signature(document_id, version_no, storage_uri, expires, signature):
            raise PermissionError("invalid_upload_signature")

        virus_scan_status = "clean" if virus_scan(content_bytes) else "infected"
        if virus_scan_status != "clean":
            raise ValueError("virus_scan_failed")

        mime_type = str(row["mime"] or "").lower()
        sanitized = True
        if mime_type in {"text/plain", "text/csv", "application/json"}:
            decoded = decode_text_bytes(content_bytes)
            sanitized_text = sanitize_text(decoded)
            sanitized = sanitized_text == decoded
            content_bytes = sanitized_text.encode("utf-8")

        sha256 = hashlib.sha256(content_bytes).hexdigest()
        document_storage.write(storage_uri, content_bytes)

        effective_thread_id = thread_id or row["thread_id"]
        effective_doc_type = doc_type or row["doc_type"] or "unknown"
        async with pool.acquire() as connection:
            await connection.execute(
                """
                update documents
                set thread_id = $2,
                    storage_uri = $3,
                    sha256 = $4,
                    byte_size = $5,
                    doc_type = $6,
                    status = $7,
                    updated_at = now()
                where id = $1
                """,
                parsed_document_id,
                effective_thread_id,
                storage_uri,
                sha256,
                len(content_bytes),
                effective_doc_type,
                "uploaded",
            )
            await connection.execute(
                """
                update document_versions
                set sha256 = $3
                where document_id = $1 and version_no = $2
                """,
                parsed_document_id,
                version_no,
                sha256,
            )

        job = await enqueue(
            QueueJob(
                document_id=document_id,
                thread_id=effective_thread_id,
                doc_type=effective_doc_type,
                payload={
                    "version_no": version_no,
                    "storage_uri": storage_uri,
                    "sanitized": sanitized,
                    "virus_scan": virus_scan_status,
                },
            )
        )

        response = {
            "document_id": document_id,
            "version_no": version_no,
            "thread_id": effective_thread_id,
            "status": "queued",
            "job_id": job.job_id,
            "storage_uri": storage_uri,
            "sanitized": sanitized,
            "virus_scan": virus_scan_status,
        }
        if process_immediately:
            processed = await self.process_pending_jobs(limit=1, document_id=document_id)
            if processed:
                response.update(processed[0])
        return response

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
        pool = await get_pool()
        parsed_document_id = uuid.UUID(document_id)
        async with pool.acquire() as connection:
            version_no = await connection.fetchval(
                "select coalesce(max(version_no), 1) from document_versions where document_id = $1",
                parsed_document_id,
            )
            version_row = await connection.fetchrow(
                "select storage_uri from document_versions where document_id = $1 and version_no = $2",
                parsed_document_id,
                version_no,
            )
        if version_row is None:
            raise KeyError(document_id)

        signed = document_storage.create_signed_upload(document_id, int(version_no), version_row["storage_uri"])
        return await self.upload_document_content(
            document_id=document_id,
            version_no=int(version_no),
            expires=int(signed["expires"]),
            signature=str(signed["signature"]),
            content_bytes=raw_text.encode("utf-8"),
            thread_id=thread_id,
            doc_type=doc_type,
            process_immediately=True,
        )

    async def process_pending_jobs(self, *, limit: Optional[int] = None, document_id: Optional[str] = None) -> list[dict[str, Any]]:
        return await drain(
            self._process_job,
            limit=limit or settings.document_queue_batch_size,
            document_id=document_id,
        )

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
                       (
                           select max(version_no)
                           from document_versions dv2
                           where dv2.document_id = d.id
                       ) as latest_version_no,
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
                order by d.updated_at desc
                """,
                thread_id,
            )
            version_rows = await connection.fetch(
                """
                select document_id, version_no, storage_uri, sha256, reason, created_at
                from document_versions
                where document_id in (
                    select id from documents where thread_id = $1
                )
                order by document_id, version_no desc
                """,
                thread_id,
            )
        versions_by_document: dict[str, list[dict[str, Any]]] = {}
        for version_row in version_rows:
            versions_by_document.setdefault(str(version_row["document_id"]), []).append(
                {
                    "version_no": version_row["version_no"],
                    "storage_uri": version_row["storage_uri"],
                    "sha256": version_row["sha256"],
                    "reason": version_row["reason"],
                    "created_at": version_row["created_at"].isoformat() if version_row["created_at"] else None,
                }
            )
        return [self._serialize_document_row(row, versions_by_document.get(str(row["id"]), [])) for row in rows]

    async def _attach_to_thread(self, thread_id: str, processed_document: dict[str, Any]) -> Optional[dict[str, Any]]:
        state = await checkpointer.latest(thread_id)
        if state is None:
            return None

        documents = [doc for doc in state.documents if doc.get("id") != processed_document["id"]]
        documents.append(processed_document)
        state.documents = documents
        state = await document_intake.run(state)
        state = await extract_facts.run(state)
        state = await reconcile.run(state)
        state = await infer_itr.run(state)
        await checkpointer.save(state)
        return {
            "thread_id": thread_id,
            "document_count": len(state.documents),
            "tax_facts": state.tax_facts,
            "reconciliation": state.reconciliation,
        }

    async def _process_job(self, job: QueueJob) -> dict[str, Any]:
        pool = await get_pool()
        parsed_document_id = uuid.UUID(job.document_id)
        version_no = int(job.payload.get("version_no", 1))
        storage_uri = str(job.payload.get("storage_uri"))

        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select id, thread_id, file_name, mime, doc_type
                from documents
                where id = $1
                """,
                parsed_document_id,
            )
        if row is None:
            raise KeyError(job.document_id)

        content_bytes = document_storage.read(storage_uri)
        payload = {
            "document_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "file_name": row["file_name"],
            "mime_type": row["mime"],
            "doc_type": job.doc_type or row["doc_type"],
            "storage_uri": storage_uri,
            "content_bytes": content_bytes,
        }
        processed = await process_document(payload)
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
                    "delete from document_pages where document_id = $1 and version_no = $2",
                    parsed_document_id,
                    version_no,
                )
                await connection.execute(
                    "delete from document_tables where document_id = $1 and version_no = $2",
                    parsed_document_id,
                    version_no,
                )
                await connection.execute(
                    "delete from document_extractions where document_id = $1 and version_no = $2",
                    parsed_document_id,
                    version_no,
                )
                await connection.execute(
                    "delete from document_entities where document_id = $1 and version_no = $2",
                    parsed_document_id,
                    version_no,
                )
                await connection.execute(
                    """
                    update documents
                    set thread_id = $2,
                        storage_uri = $3,
                        doc_type = $4,
                        classification_confidence = $5,
                        status = $6,
                        parsed_at = now(),
                        updated_at = now()
                    where id = $1
                    """,
                    parsed_document_id,
                    row["thread_id"],
                    storage_uri,
                    processed.get("document_type", row["doc_type"] or "unknown"),
                    processed.get("classification_confidence", 0),
                    "parsed",
                )
                for page in processed.get("pages", []):
                    await connection.execute(
                        """
                        insert into document_pages (
                            id, document_id, version_no, page_no, text, ocr_used, ocr_confidence
                        )
                        values ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        uuid.uuid4(),
                        parsed_document_id,
                        version_no,
                        int(page.get("page_no", 1)),
                        page.get("text"),
                        bool(page.get("ocr_used", False)),
                        page.get("ocr_confidence"),
                    )
                for index, table_rows in enumerate(processed.get("tables", []), start=1):
                    await connection.execute(
                        """
                        insert into document_tables (id, document_id, version_no, page_no, rows)
                        values ($1, $2, $3, $4, $5::jsonb)
                        """,
                        uuid.uuid4(),
                        parsed_document_id,
                        version_no,
                        index,
                        json.dumps(table_rows, sort_keys=True),
                    )
                await connection.execute(
                    """
                    insert into document_extractions (
                        id, document_id, version_no, extractor_name, extractor_version,
                        raw_json, normalized_json, confidence
                    )
                    values ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
                    """,
                    uuid.uuid4(),
                    parsed_document_id,
                    version_no,
                    processed.get("parsed", {}).get("parser", "unknown"),
                    PIPELINE_VERSION,
                    json.dumps(
                        {
                            "classification_confidence": processed.get("classification_confidence"),
                            "parser_output": processed.get("parsed", {}),
                            "warnings": processed.get("parsed", {}).get("warnings", []),
                            "tables": processed.get("tables", []),
                            "processing_summary": processed.get("processing_summary", {}),
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
                            id, document_id, version_no, page_no, entity_type, value, normalized, confidence
                        )
                        values ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        uuid.uuid4(),
                        parsed_document_id,
                        version_no,
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
            "storage_uri": storage_uri,
            "version_no": version_no,
            "sanitized": True,
            "sanitized": bool(job.payload.get("sanitized", True)),
            "virus_scan": job.payload.get("virus_scan", "clean"),
            "parser": processed.get("parsed", {}).get("parser", "unknown"),
            "parser_confidence": extraction_confidence,
            "classification_confidence": processed.get("classification_confidence", 0),
            "normalized_fields": normalized_fields,
            "entities": entities,
            "extraction_warnings": processed.get("parsed", {}).get("warnings", []),
            "sha256": hashlib.sha256(content_bytes).hexdigest(),
        }

        attached_summary = None
        if row["thread_id"]:
            attached_summary = await self._attach_to_thread(str(row["thread_id"]), processed_document)

        return {
            "document_id": str(row["id"]),
            "thread_id": row["thread_id"],
            "status": "parsed",
            "document_type": processed_document["type"],
            "parser": processed_document["parser"],
            "classification_confidence": processed_document["classification_confidence"],
            "normalized_fields": normalized_fields,
            "entities": entities,
            "warnings": processed_document["extraction_warnings"],
            "version_no": version_no,
            "attached_thread": attached_summary,
        }

    def _serialize_document_row(self, row: Record, versions: list[dict[str, Any]]) -> dict[str, Any]:
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
            "latest_version_no": row["latest_version_no"],
            "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
            "parsed_at": row["parsed_at"].isoformat() if row["parsed_at"] else None,
            "normalized_fields": json.loads(normalized_text) if normalized_text else {},
            "versions": versions,
        }


document_service = DocumentService()