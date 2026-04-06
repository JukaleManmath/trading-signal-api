import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # symbol → list of connected WebSocket clients
        self.connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def subscribe(self, symbol: str, ws: WebSocket) -> None:
        await ws.accept()
        self.connections[symbol.upper()].append(ws)
        logger.info("websocket_subscribed", extra={"symbol": symbol.upper()})

    def unsubscribe(self, symbol: str, ws: WebSocket) -> None:
        symbol = symbol.upper()
        self.connections[symbol] = [
            c for c in self.connections[symbol] if c is not ws
        ]
        logger.info("websocket_unsubscribed", extra={"symbol": symbol})

    async def broadcast(self, symbol: str, message: dict) -> None:
        symbol = symbol.upper()
        dead: list[WebSocket] = []
        for ws in self.connections[symbol]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unsubscribe(symbol, ws)


manager = ConnectionManager()
