from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "hello", "payload": "backend_connected"})
    while True:
      data = await websocket.receive_json()
      await websocket.send_json({"type": "echo", "payload": data})
