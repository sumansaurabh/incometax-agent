from __future__ import annotations

import hmac
import time
from datetime import timedelta
from hashlib import sha256

from itx_backend.config import settings


class MinioDocumentStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        upload_secret: str,
    ) -> None:
        try:
            from minio import Minio
        except ImportError as exc:  # pragma: no cover - exercised only when runtime deps are missing.
            raise RuntimeError("minio package is required when ITX_DOCUMENT_STORAGE_BACKEND=minio") from exc

        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket
        self._secret = upload_secret.encode("utf-8")

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def create_signed_upload(self, document_id: str, version_no: int, storage_uri: str) -> dict[str, int | str]:
        expires = int(time.time()) + settings.document_upload_ttl_seconds
        signature = self._sign(document_id, version_no, expires, storage_uri)
        result: dict[str, int | str] = {
            "expires": expires,
            "signature": signature,
        }
        try:
            result["direct_upload_url"] = self._client.presigned_put_object(
                self._bucket,
                storage_uri,
                expires=timedelta(seconds=settings.document_upload_ttl_seconds),
            )
        except Exception:
            # The backend upload endpoint remains available even when direct
            # presigning fails because local dev often runs before MinIO is up.
            pass
        return result

    def create_presigned_download(self, storage_uri: str, *, ttl_seconds: int = 900) -> str:
        return self._client.presigned_get_object(
            self._bucket,
            storage_uri,
            expires=timedelta(seconds=ttl_seconds),
        )

    def verify_signature(self, document_id: str, version_no: int, storage_uri: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        expected = self._sign(document_id, version_no, expires, storage_uri)
        return hmac.compare_digest(expected, signature)

    def write(self, storage_uri: str, content: bytes) -> str:
        from io import BytesIO

        self.ensure_bucket()
        self._client.put_object(self._bucket, storage_uri, BytesIO(content), length=len(content))
        return storage_uri

    def read(self, storage_uri: str) -> bytes:
        response = self._client.get_object(self._bucket, storage_uri)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, storage_uri: str) -> bool:
        self._client.remove_object(self._bucket, storage_uri)
        return True

    def _sign(self, document_id: str, version_no: int, expires: int, storage_uri: str) -> str:
        payload = f"{document_id}:{version_no}:{expires}:{storage_uri}".encode("utf-8")
        return hmac.new(self._secret, payload, sha256).hexdigest()


def build_minio_document_storage() -> MinioDocumentStorage:
    return MinioDocumentStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
        upload_secret=settings.document_upload_secret,
    )
