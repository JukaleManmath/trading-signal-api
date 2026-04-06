import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/prices/{symbol}")
async def price_stream(symbol: str, websocket: WebSocket) -> None:
    """
    WebSocket endpoint — clients connect here to receive live price ticks.

    Flow:
      1. Client connects → registered in ConnectionManager under symbol
      2. kafka_broadcaster pushes price events → manager.broadcast() sends to this socket
      3. Client disconnects → unregistered automatically
    """
    await manager.subscribe(symbol, websocket)
    try:
        while True:
            # Keep the connection alive. We don't expect client messages,
            # but we must await something so the coroutine doesn't exit.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.unsubscribe(symbol, websocket)
        logger.info("websocket_disconnected", extra={"symbol": symbol.upper()})
