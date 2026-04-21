from __future__ import annotations

import base64
import binascii
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from itx_backend.security.request_auth import get_request_auth, require_thread_state
from itx_backend.services.documents import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


class UploadInitRequest(BaseModel):
    file_name: str
    mime_type: str
    thread_id: Optional[str] = None
    doc_type: Optional[str] = None
    document_id: Optional[str] = None
    reason: Optional[str] = None


class DocumentIngestRequest(BaseModel):
    raw_text: str
    thread_id: Optional[str] = None
    doc_type: Optional[str] = None


class DocumentContentUploadRequest(BaseModel):
    content_base64: Optional[str] = None
    content_text: Optional[str] = None
    thread_id: Optional[str] = None
    doc_type: Optional[str] = None
    process_immediately: bool = True


class QueueRunRequest(BaseModel):
    limit: int = 10


async def _require_document_access(document_id: str) -> str:
    thread_id = await document_service.get_document_thread_id(document_id)
    if thread_id is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    await require_thread_state(thread_id)
    return thread_id


@router.post("/signed-upload")
async def signed_upload(payload: UploadInitRequest) -> dict[str, Optional[str]]:
    if payload.document_id:
        existing_thread_id = await _require_document_access(payload.document_id)
        if payload.thread_id and payload.thread_id != existing_thread_id:
            raise HTTPException(status_code=403, detail="thread_forbidden")
    else:
        if not payload.thread_id:
            raise HTTPException(status_code=400, detail="thread_id_required")
        await require_thread_state(payload.thread_id)
    try:
        return await document_service.create_upload(
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            thread_id=payload.thread_id,
            doc_type=payload.doc_type,
            document_id=payload.document_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document_not_found") from exc


@router.put("/{document_id}/content")
async def upload_document_content(
    document_id: str,
    version_no: int,
    expires: int,
    signature: str,
    payload: DocumentContentUploadRequest,
) -> dict:
    if not payload.content_base64 and payload.content_text is None:
        raise HTTPException(status_code=400, detail="content_base64_or_content_text_required")
    existing_thread_id = await _require_document_access(document_id)
    if payload.thread_id and payload.thread_id != existing_thread_id:
        raise HTTPException(status_code=403, detail="thread_forbidden")
    try:
        content_bytes = (
            base64.b64decode(payload.content_base64) if payload.content_base64 else payload.content_text.encode("utf-8")
        )
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail="invalid_base64_content") from exc

    try:
        return await document_service.upload_document_content(
            document_id=document_id,
            version_no=version_no,
            expires=expires,
            signature=signature,
            content_bytes=content_bytes,
            thread_id=payload.thread_id or existing_thread_id,
            doc_type=payload.doc_type,
            process_immediately=payload.process_immediately,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document_not_found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{document_id}/ingest")
async def ingest_uploaded_document(document_id: str, payload: DocumentIngestRequest) -> dict:
    existing_thread_id = await _require_document_access(document_id)
    if payload.thread_id and payload.thread_id != existing_thread_id:
        raise HTTPException(status_code=403, detail="thread_forbidden")
    try:
        return await document_service.ingest_document(
            document_id=document_id,
            raw_text=payload.raw_text,
            thread_id=payload.thread_id or existing_thread_id,
            doc_type=payload.doc_type,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/queue/run")
async def run_document_queue(payload: QueueRunRequest) -> dict[str, object]:
    get_request_auth(required=True)
    processed = await document_service.process_pending_jobs(limit=payload.limit)
    return {
        "processed": processed,
        "count": len(processed),
    }


@router.get("/thread/{thread_id}")
async def list_thread_documents(thread_id: str) -> dict[str, object]:
    await require_thread_state(thread_id)
    return {
        "thread_id": thread_id,
        "documents": await document_service.list_documents(thread_id),
    }
