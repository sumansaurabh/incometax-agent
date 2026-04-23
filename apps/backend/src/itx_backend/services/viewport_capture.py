from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ViewportCaptureTimeout(Exception):
    pass


class ViewportCaptureError(Exception):
    pass


class _Socket:
    """Minimal protocol the service relies on. FastAPI WebSocket satisfies this."""

    async def send_json(self, data: dict[str, Any]) -> None:  # pragma: no cover - protocol shim
        raise NotImplementedError


class ViewportCaptureService:
    """Bridges the `capture_viewport` backend tool to the browser extension over the existing
    chat websocket connection.

    The agent tool calls `request_capture(user_id, ...)` which:
    1. Posts a `capture_viewport_request` down the user's open socket(s).
    2. Awaits a `capture_viewport_result` keyed by the same request_id.
    3. Returns the image bytes (base64) or raises ViewportCaptureError / ViewportCaptureTimeout.

    If the same user has multiple open sockets (e.g., two Chrome profiles), we send to all and
    resolve on the first result. The extension does not capture unless its active tab passes the
    trust check, so racing is safe.
    """

    def __init__(self) -> None:
        self._sockets: dict[str, set[_Socket]] = {}
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def attach(self, user_id: str, socket: _Socket) -> None:
        async with self._lock:
            self._sockets.setdefault(user_id, set()).add(socket)

    async def detach(self, user_id: str, socket: _Socket) -> None:
        async with self._lock:
            sockets = self._sockets.get(user_id)
            if sockets is None:
                return
            sockets.discard(socket)
            if not sockets:
                self._sockets.pop(user_id, None)

    def has_socket(self, user_id: str) -> bool:
        sockets = self._sockets.get(user_id)
        return bool(sockets)

    async def handle_result(self, payload: dict[str, Any]) -> None:
        """Called by the websocket handler when the extension sends capture_viewport_result."""
        request_id = str(payload.get("request_id") or "")
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return
        future.set_result(payload)

    async def request_capture(self, *, user_id: str, timeout: float = 8.0) -> dict[str, Any]:
        sockets = list(self._sockets.get(user_id, set()))
        if not sockets:
            raise ViewportCaptureError("extension_not_connected")

        request_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future

        message = {
            "type": "capture_viewport_request",
            "payload": {"request_id": request_id},
        }

        sent = 0
        for socket in sockets:
            try:
                await socket.send_json(message)
                sent += 1
            except Exception:  # noqa: BLE001 — one failed socket shouldn't block the rest
                logger.exception("viewport_capture.send_failed", extra={"user_id": user_id})
        if sent == 0:
            self._pending.pop(request_id, None)
            raise ViewportCaptureError("send_failed")

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise ViewportCaptureTimeout("capture_timed_out") from exc

        if not result.get("ok"):
            raise ViewportCaptureError(str(result.get("error") or "capture_failed"))

        media_type = str(result.get("media_type") or "image/jpeg")
        data_base64 = str(result.get("data_base64") or "")
        if not data_base64:
            raise ViewportCaptureError("empty_image")

        return {
            "media_type": media_type,
            "data_base64": data_base64,
            "size_bytes": int(result.get("size_bytes") or 0),
            "viewport": result.get("viewport") or {},
            "captured_at": result.get("captured_at"),
        }


viewport_capture_service = ViewportCaptureService()
