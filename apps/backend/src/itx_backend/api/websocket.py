from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from itx_backend.services.auth_runtime import AuthError, auth_runtime

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
      await websocket.send_json({"type": "echo", "payload": data})
  except WebSocketDisconnect:
    return
