from __future__ import annotations

import hmac
import time
from hashlib import sha256
from pathlib import Path

from itx_backend.config import settings


class LocalDocumentStorage:
    def __init__(self, root: str, secret: str) -> None:
        self._root = Path(root)
        self._secret = secret.encode("utf-8")

    def create_signed_upload(self, document_id: str, version_no: int, storage_uri: str) -> dict[str, int | str]:
        expires = int(time.time()) + settings.document_upload_ttl_seconds
        signature = self._sign(document_id, version_no, expires, storage_uri)
        return {
            "expires": expires,
            "signature": signature,
        }

    def verify_signature(self, document_id: str, version_no: int, storage_uri: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        expected = self._sign(document_id, version_no, expires, storage_uri)
        return hmac.compare_digest(expected, signature)

    def write(self, storage_uri: str, content: bytes) -> Path:
        path = self._resolve(storage_uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def read(self, storage_uri: str) -> bytes:
        return self._resolve(storage_uri).read_bytes()

    def delete(self, storage_uri: str) -> bool:
        path = self._resolve(storage_uri)
        if not path.exists():
            return False
        path.unlink()
        self._prune_empty_parents(path.parent)
        return True

    def _sign(self, document_id: str, version_no: int, expires: int, storage_uri: str) -> str:
        payload = f"{document_id}:{version_no}:{expires}:{storage_uri}".encode("utf-8")
        return hmac.new(self._secret, payload, sha256).hexdigest()

    def _resolve(self, storage_uri: str) -> Path:
        candidate = (self._root / storage_uri).resolve()
        root = self._root.resolve()
        if root not in candidate.parents and candidate != root:
            raise ValueError("invalid_storage_uri")
        return candidate

    def _prune_empty_parents(self, candidate: Path) -> None:
        root = self._root.resolve()
        current = candidate.resolve()
        while current != root:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent


document_storage = LocalDocumentStorage(
    root=settings.document_storage_root,
    secret=settings.document_upload_secret,
)