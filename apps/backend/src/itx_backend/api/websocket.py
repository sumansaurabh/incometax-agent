from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.services.auth_runtime import AuthError, auth_runtime
from itx_backend.services.chat import chat_service

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
  access_token = websocket.query_params.get("access_token")
  device_id = websocket.query_params.get("device_id", "")
  await websocket.accept()
  if not access_token:
    await websocket.close(code=4401, reason="authorization_required")
    return
  try:
    auth_context = await auth_runtime.authenticate_access_token(access_token, device_id)
  except AuthError as exc:
    await websocket.close(code=4403 if exc.status_code == 403 else 4401, reason=exc.code)
    return
  await websocket.send_json(
    {
      "type": "hello",
      "payload": {
        "status": "backend_connected",
        "user_id": auth_context.user_id,
        "device_id": auth_context.device_id,
      },
    }
  )
  try:
    while True:
      data = await websocket.receive_json()
      if data.get("type") == "chat_message":
        payload = data.get("payload") or {}
        thread_id = str(payload.get("thread_id") or payload.get("threadId") or "")
        text = str(payload.get("text") or payload.get("message") or "")
        state = await checkpointer.latest(thread_id) if thread_id else None
        if not state or state.user_id != auth_context.user_id:
          await websocket.send_json({"type": "chat_error", "payload": {"error": "thread_forbidden"}})
          continue
        response = await chat_service.handle_message(
          thread_id=thread_id,
          message=text,
          context=dict(payload.get("context") or {}),
        )
        await websocket.send_json({"type": "chat_response", "payload": response["agent_message"]})
        continue
      await websocket.send_json({"type": "echo", "payload": data})
  except WebSocketDisconnect:
    return
