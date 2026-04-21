from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from itx_backend.services.documents import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


class UploadInitRequest(BaseModel):
    file_name: str
    mime_type: str
    thread_id: Optional[str] = None
    doc_type: Optional[str] = None


class DocumentIngestRequest(BaseModel):
    raw_text: str
    thread_id: Optional[str] = None
    doc_type: Optional[str] = None


@router.post("/signed-upload")
async def signed_upload(payload: UploadInitRequest) -> dict[str, Optional[str]]:
    return await document_service.create_upload(
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        thread_id=payload.thread_id,
        doc_type=payload.doc_type,
    )


@router.post("/{document_id}/ingest")
async def ingest_uploaded_document(document_id: str, payload: DocumentIngestRequest) -> dict:
    try:
        return await document_service.ingest_document(
            document_id=document_id,
            raw_text=payload.raw_text,
            thread_id=payload.thread_id,
            doc_type=payload.doc_type,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/thread/{thread_id}")
async def list_thread_documents(thread_id: str) -> dict[str, object]:
    return {
        "thread_id": thread_id,
        "documents": await document_service.list_documents(thread_id),
    }
