import uuid

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/documents", tags=["documents"])


class UploadInitRequest(BaseModel):
    file_name: str
    mime_type: str


@router.post("/signed-upload")
def signed_upload(payload: UploadInitRequest) -> dict[str, str]:
    doc_id = str(uuid.uuid4())
    return {
        "document_id": doc_id,
        "upload_url": f"https://example-upload.local/{doc_id}/{payload.file_name}"
    }
