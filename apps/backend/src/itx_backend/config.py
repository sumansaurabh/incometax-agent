import os

from pydantic import BaseModel


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    auth_access_ttl_seconds: int = int(os.getenv("ITX_AUTH_ACCESS_TTL_SECONDS", "900"))
    auth_refresh_ttl_seconds: int = int(os.getenv("ITX_AUTH_REFRESH_TTL_SECONDS", str(30 * 24 * 60 * 60)))
    retention_purge_days: int = int(os.getenv("ITX_RETENTION_PURGE_DAYS", "30"))
    retention_sweep_interval_seconds: int = int(os.getenv("ITX_RETENTION_SWEEP_INTERVAL_SECONDS", "300"))
    rate_limit_window_seconds: int = int(os.getenv("ITX_RATE_LIMIT_WINDOW_SECONDS", "60"))
    redis_url: str = os.getenv("ITX_REDIS_URL", "")
    redis_key_prefix: str = os.getenv("ITX_REDIS_KEY_PREFIX", "itx")
    otel_service_name: str = os.getenv("ITX_OTEL_SERVICE_NAME", "itx-backend")
    otel_exporter_otlp_endpoint: str = os.getenv("ITX_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    otel_exporter_otlp_headers: str = os.getenv("ITX_OTEL_EXPORTER_OTLP_HEADERS", "")
    langfuse_enabled: bool = _env_bool("ITX_LANGFUSE_ENABLED", False)
    langfuse_host: str = os.getenv("ITX_LANGFUSE_HOST", "https://cloud.langfuse.com")
    langfuse_public_key: str = os.getenv("ITX_LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("ITX_LANGFUSE_SECRET_KEY", "")
    langfuse_otlp_endpoint: str = os.getenv("ITX_LANGFUSE_OTLP_ENDPOINT", "")
    ai_provider: str = os.getenv("ITX_AI_PROVIDER", "")
    ai_model: str = os.getenv("ITX_AI_MODEL", "")
    ai_api_key: str = os.getenv("ITX_AI_API_KEY", os.getenv("OPENAI_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")))
    ai_base_url: str = os.getenv("ITX_AI_BASE_URL", "")


settings = Settings()
