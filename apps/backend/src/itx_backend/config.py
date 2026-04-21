import os

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "IncomeTax Agent Backend"
    app_version: str = "0.1.0"
    environment: str = os.getenv("ITX_ENVIRONMENT", "dev")
    websocket_path: str = os.getenv("ITX_WEBSOCKET_PATH", "/ws")
    database_url: str = os.getenv("ITX_DATABASE_URL", "postgresql://itx:itx@localhost:5432/itx")
    database_min_pool_size: int = int(os.getenv("ITX_DATABASE_MIN_POOL_SIZE", "1"))
    database_max_pool_size: int = int(os.getenv("ITX_DATABASE_MAX_POOL_SIZE", "5"))
    document_storage_root: str = os.getenv("ITX_DOCUMENT_STORAGE_ROOT", "/tmp/itx-documents")
    document_upload_secret: str = os.getenv("ITX_DOCUMENT_UPLOAD_SECRET", "dev-document-upload-secret")
    document_upload_ttl_seconds: int = int(os.getenv("ITX_DOCUMENT_UPLOAD_TTL_SECONDS", "900"))
    document_queue_batch_size: int = int(os.getenv("ITX_DOCUMENT_QUEUE_BATCH_SIZE", "10"))


settings = Settings()
